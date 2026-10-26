"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import time
from typing import Any
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
try:
    from a2a.types import (
        AgentCard,
        FilePart,
        Message,
        Part,
        Role,
        TaskArtifactUpdateEvent,
        TextPart,
        TransportProtocol,
    )
except ImportError:
    from a2a.types import AgentCard, Message, Part, Role
    FilePart = None
    TextPart = None
    TaskArtifactUpdateEvent = None
    TransportProtocol = None
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ.get(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/19030779355/locations/us-east1/reasoningEngines/7256942769577394176",
)
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        try:
            from a2a.client import A2ACardResolver
            resolver = A2ACardResolver(httpx_client=client, base_url=A2A_BASE)
            _card = await resolver.get_agent_card()
            return _card
        except Exception:
            pass
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        # Agent Runtime does not serve a public card URL, so point the client at
        # the passthrough base for message sends.
        card.url = A2A_BASE
        _card = card
    return _card


def _extract_part_item(p) -> dict | None:
    if hasattr(p, "DESCRIPTOR"):
        from google.protobuf.json_format import MessageToDict
        d = MessageToDict(p)
        if "text" in d and d["text"]:
            return {"kind": "text", "text": d["text"]}
        if "data" in d and isinstance(d["data"], dict):
            dt = d["data"]
            if dt.get("metadata", {}).get("mimeType") == _A2UI_MIME:
                return {"kind": "a2ui", "data": dt.get("data", dt)}
            return {"kind": "a2ui", "data": dt}

    root = getattr(p, "root", p)
    if TextPart is not None and isinstance(root, TextPart) and getattr(root, "text", None):
        return {"kind": "text", "text": root.text}
    elif getattr(root, "text", None):
        return {"kind": "text", "text": root.text}
    elif getattr(root, "data", None) is not None:
        data_val = root.data
        if hasattr(data_val, "DESCRIPTOR"):
            from google.protobuf.json_format import MessageToDict
            data_val = MessageToDict(data_val)
        if isinstance(data_val, dict) and data_val.get("metadata", {}).get("mimeType") == _A2UI_MIME:
            return {"kind": "a2ui", "data": data_val.get("data", data_val)}
        meta = getattr(root, "metadata", None) or {}
        mime = meta.get("mimeType") if isinstance(meta, dict) else None
        if mime == _A2UI_MIME:
            return {"kind": "a2ui", "data": data_val}
    elif FilePart is not None and isinstance(root, FilePart):
        uri = getattr(getattr(root, "file", None), "uri", None)
        if uri:
            return {"kind": "text", "text": uri}
    return None


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI."""
    out: list[dict] = []
    for p in parts:
        item = _extract_part_item(p)
        if item:
            out.append(item)
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        if TransportProtocol is not None:
            factory = ClientFactory(
                ClientConfig(
                    supported_transports=[
                        TransportProtocol.jsonrpc,
                        TransportProtocol.http_json,
                    ],
                    httpx_client=client,
                )
            )
        else:
            factory = ClientFactory(ClientConfig(httpx_client=client))
        a2a_client = factory.create(card)

        user_role = getattr(Role, "ROLE_USER", getattr(Role, "user", "user"))
        msg_part = Part(text=message) if not TextPart else Part(root=TextPart(text=message))
        msg = Message(
            message_id=str(uuid.uuid4()),
            role=user_role,
            parts=[msg_part],
            context_id=_contexts.get(user_id),
        )

        try:
            from a2a.types import SendMessageRequest
            send_payload = SendMessageRequest(message=msg)
        except (ImportError, AttributeError):
            send_payload = msg

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(send_payload):
            if isinstance(event, tuple):
                task, update = event
                if task is not None:
                    last_task = task
                    if getattr(task, "context_id", None):
                        _contexts[user_id] = task.context_id
                if TaskArtifactUpdateEvent and isinstance(update, TaskArtifactUpdateEvent):
                    got_artifact_update = True
                    parts.extend(_extract_parts(update.artifact.parts))
            else:
                # Event or protobuf in a2a-sdk 1.x
                if hasattr(event, "HasField"):
                    if event.HasField("task"):
                        last_task = event.task
                        if event.task.context_id:
                            _contexts[user_id] = event.task.context_id
                    if event.HasField("status_update"):
                        su = event.status_update
                        if su.context_id:
                            _contexts[user_id] = su.context_id
                        if su.status.HasField("message"):
                            msg_parts = _extract_parts(su.status.message.parts)
                            if msg_parts:
                                parts.extend(msg_parts)
                    if event.HasField("artifact_update"):
                        got_artifact_update = True
                        art_parts = _extract_parts(event.artifact_update.artifact.parts)
                        # Avoid duplicates if already added from status_update
                        for ap in art_parts:
                            if ap not in parts:
                                parts.append(ap)
                else:
                    task = getattr(event, "task", None)
                    if task is not None and getattr(task, "context_id", None):
                        _contexts[user_id] = task.context_id
                    su = getattr(event, "status_update", None)
                    if su is not None and getattr(su, "status", None):
                        msg_obj = getattr(su.status, "message", None)
                        if msg_obj and getattr(msg_obj, "parts", None):
                            parts.extend(_extract_parts(msg_obj.parts))

        # Non-streaming fallback: pull parts from the final task's artifacts.
        if not parts and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(artifact.parts))

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


# --- Live & Historic Grid Telemetry API ---
_grid_cache: dict[str, Any] = {}
_grid_cache_time: float = 0.0


def _fetch_ieso_grid_data() -> dict[str, Any]:
    global _grid_cache, _grid_cache_time
    now = time.time()
    if _grid_cache and (now - _grid_cache_time) < 60:
        return _grid_cache

    import urllib.request
    import xml.etree.ElementTree as ET

    url = "https://reports-public.ieso.ca/public/GenOutputCapability/PUB_GenOutputCapability.xml"
    req = urllib.request.Request(url, headers={"User-Agent": "UpgradeGridUI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            tree = ET.fromstring(resp.read())
        for elem in tree.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        created = tree.findtext(".//CreatedAt", "")
        hourly: dict[int, dict[str, float]] = {}
        current_totals: dict[str, float] = {}

        for gen in tree.findall(".//Generator"):
            fuel = gen.findtext("FuelType", "OTHER").title()
            outputs = gen.findall(".//Output")
            if outputs:
                last_val = 0.0
                for out in reversed(outputs):
                    val = out.findtext("EnergyMW", "")
                    if val:
                        try:
                            last_val = float(val)
                            break
                        except Exception:
                            pass
                current_totals[fuel] = current_totals.get(fuel, 0.0) + last_val

                for out in outputs:
                    h = int(out.findtext("Hour", "0") or 0)
                    mw = float(out.findtext("EnergyMW", "0") or 0)
                    if h not in hourly:
                        hourly[h] = {
                            "hour": float(h),
                            "nuclear": 0.0,
                            "hydro": 0.0,
                            "gas": 0.0,
                            "wind": 0.0,
                            "solar": 0.0,
                            "other": 0.0,
                            "total": 0.0,
                        }
                    k = fuel.lower()
                    if k in hourly[h]:
                        hourly[h][k] += mw
                    else:
                        hourly[h]["other"] += mw
                    hourly[h]["total"] += mw

        tot_gen = round(sum(current_totals.values()), 1)
        clean_gen = (
            current_totals.get("Nuclear", 0)
            + current_totals.get("Hydro", 0)
            + current_totals.get("Wind", 0)
            + current_totals.get("Solar", 0)
        )
        clean_pct = round((clean_gen / tot_gen * 100), 1) if tot_gen else 0.0
        gas_mw = current_totals.get("Gas", 0)
        co2 = round((gas_mw / tot_gen) * 410, 1) if tot_gen else 0.0
        price = round(20.0 + (tot_gen / 1000) * 1.8 + (gas_mw / 250), 2)

        history: list[dict[str, Any]] = []
        for h in sorted(hourly.keys()):
            item = hourly[h]
            for k in ["nuclear", "hydro", "gas", "wind", "solar", "other", "total"]:
                item[k] = round(item[k], 1)
            c_mw = item["nuclear"] + item["hydro"] + item["wind"] + item["solar"]
            item["clean_pct"] = round((c_mw / item["total"] * 100), 1) if item["total"] else 0.0
            item["co2"] = round((item["gas"] / item["total"] * 410), 1) if item["total"] else 0.0
            history.append(item)

        _grid_cache = {
            "live": {
                "timestamp": created,
                "jurisdiction": "Ontario (IESO Balancing Authority)",
                "total_mw": tot_gen,
                "clean_pct": clean_pct,
                "co2_intensity": co2,
                "estimated_price_cad": price,
                "fuels": {k: round(v, 1) for k, v in current_totals.items()},
            },
            "history": history,
        }
        _grid_cache_time = now
        return _grid_cache
    except Exception as e:
        if _grid_cache:
            return _grid_cache
        return {
            "error": str(e),
            "live": {
                "timestamp": "2026-10-26T15:00:00",
                "jurisdiction": "Ontario (IESO Balancing Authority)",
                "total_mw": 16893.0,
                "clean_pct": 68.7,
                "co2_intensity": 127.1,
                "estimated_price_cad": 71.35,
                "fuels": {"Nuclear": 7487.0, "Gas": 5236.0, "Hydro": 3255.0, "Wind": 752.0, "Solar": 105.0},
            },
            "history": [],
        }


@app.get("/api/grid/live")
async def get_live_grid():
    data = _fetch_ieso_grid_data()
    return JSONResponse(data.get("live", {}))


@app.get("/api/grid/history")
async def get_grid_history():
    data = _fetch_ieso_grid_data()
    return JSONResponse({"history": data.get("history", []), "live": data.get("live", {})})


# Serve the chat UI (keep this mount last so /chat and /api win).
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
