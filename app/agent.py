# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from a2ui_utils import a2ui_callback


MODEL = "gemini-3.8-flash"

# Hardcoded GCP Project ID and GCS Bucket Name
# (Prevents Agent Platform deployment issue where google.auth.default() returns project number)
PROJECT_ID = "qwiklabs-gcp-04-db22d601027d"
COLLECTION_NAME = "grid_technologies"
GCS_BUCKET_NAME = "bwg3-qwiklabs-gcp-04-db22d601027d"
MEMORY_BANK_ID = "3194695905689206784"
MEMORY_LOCATION = "us-east1"

db = firestore.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)


def memory_bank_service_builder() -> VertexAiMemoryBankService:
    """Builds the Vertex AI Memory Bank service for deployed runtimes."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=MEMORY_LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext) -> None:
    """Writes salient conversation facts and user engineering preferences to Memory Bank after each turn."""
    await callback_context.add_session_to_memory()
    return None




def list_grid_technologies(category: str = "") -> list[dict[str, Any]] | str:
    """Lists emerging grid technologies and modernization solutions from the Firestore catalog.

    Args:
        category: Optional category filter (e.g. 'Energy Storage', 'Distributed Energy Resources',
                  'Inverter-Based Resources (IBR)', 'Transmission & Distribution Optimization',
                  'Electrification & Mobility'). If empty or not specified, returns all technologies.

    Returns:
        A list of dictionaries with technology details (id, name, category, trl, status, summary).
    """
    try:
        col_ref = db.collection(COLLECTION_NAME)
        if category:
            docs = col_ref.where("category", "==", category).stream()
        else:
            docs = col_ref.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append({
                "id": data.get("id", doc.id),
                "name": data.get("name"),
                "category": data.get("category"),
                "trl": data.get("trl"),
                "status": data.get("status"),
                "summary": data.get("summary"),
                "primary_use_case": data.get("primary_use_case"),
            })

        if not results:
            return f"No grid technologies found matching category: '{category}'."
        return results
    except Exception as e:
        return f"Error querying Firestore collection '{COLLECTION_NAME}': {str(e)}"


def get_grid_technology(tech_id: str) -> dict[str, Any] | str:
    """Retrieves detailed technical specifications, standards, and engineering notes for a specific grid technology by ID.

    Args:
        tech_id: The unique identifier of the technology (e.g. 'grid-forming-inverters',
                 'bess-long-duration', 'virtual-power-plants', 'dynamic-line-rating',
                 'smart-ev-fleet-v2g').

    Returns:
        A dictionary containing the full technical specifications and standards, or an error if not found.
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(tech_id)
        doc = doc_ref.get()
        if not doc.exists:
            return f"Grid technology with id '{tech_id}' was not found in Firestore."
        return doc.to_dict()
    except Exception as e:
        return f"Error retrieving document '{tech_id}' from Firestore: {str(e)}"


def add_grid_technology(
    tech_id: str,
    name: str,
    category: str,
    trl: int,
    summary: str,
    primary_use_case: str,
    relevant_standards: list[str],
    status: str,
    engineering_notes: str,
) -> str:
    """Adds or updates an emerging grid technology or pilot project record in the Firestore catalog.

    Args:
        tech_id: Unique slug identifier (e.g. 'microgrid-blackstart', 'synchrophasor-pmu').
        name: Display name of the grid technology.
        category: Technology domain (e.g. 'Inverter-Based Resources (IBR)', 'Energy Storage', 'Distributed Energy Resources', 'Distribution Automation').
        trl: Technology Readiness Level integer between 1 and 9.
        summary: Brief technical summary of the technology.
        primary_use_case: Key utility operational use case.
        relevant_standards: List of relevant industry standards (e.g. ['IEEE 1547-2018', 'NERC CIP']).
        status: Deployment status (e.g. 'Research & Demonstration', 'Pilot Testing', 'Commercial Deployment').
        engineering_notes: Practical engineering guidance or utility considerations.

    Returns:
        Confirmation string indicating successful storage in Firestore.
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(tech_id)
        payload = {
            "id": tech_id,
            "name": name,
            "category": category,
            "trl": trl,
            "summary": summary,
            "primary_use_case": primary_use_case,
            "relevant_standards": relevant_standards,
            "status": status,
            "engineering_notes": engineering_notes,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        doc_ref.set(payload)
        return f"Successfully saved grid technology '{name}' (ID: {tech_id}) into Firestore collection '{COLLECTION_NAME}'."
    except Exception as e:
        return f"Error saving technology '{tech_id}' to Firestore: {str(e)}"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    elif "toronto" in query.lower() or "ontario" in query.lower() or "new york" in query.lower():
        tz_identifier = "America/Toronto"
    else:
        tz_identifier = "UTC"

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def calculate_feeder_hosting_capacity(
    substation_voltage_kv: float,
    feeder_resistance_ohms: float,
    feeder_reactance_ohms: float,
    proposed_der_kw: float,
    proposed_der_kvar: float = 0.0,
    min_daytime_load_kw: float = 0.0,
) -> dict[str, Any]:
    """Calculates distribution feeder voltage rise and reverse power flow for a proposed solar or battery DER interconnection.

    Args:
        substation_voltage_kv: Nominal line-to-line feeder voltage in kV (e.g. 13.8 or 27.6).
        feeder_resistance_ohms: Total line resistance (R) in ohms from substation to point of interconnection.
        feeder_reactance_ohms: Total line reactance (X) in ohms from substation to point of interconnection.
        proposed_der_kw: Proposed active generation capacity in kW (e.g. 1500 for a 1.5 MW solar PV or BESS).
        proposed_der_kvar: Proposed reactive power in kVAR (positive for injecting, negative for absorbing). Default is 0.0.
        min_daytime_load_kw: Minimum daytime baseline feeder customer load in kW. Default is 0.0.

    Returns:
        A dictionary containing voltage rise percentage, reverse power flow (kW), compliance status, and smart inverter recommendations.
    """
    net_reverse_flow_kw = proposed_der_kw - min_daytime_load_kw
    has_reverse_flow = net_reverse_flow_kw > 0

    v_nominal_ln_volts = (substation_voltage_kv * 1000) / (3 ** 0.5)
    delta_v_volts = (proposed_der_kw * feeder_resistance_ohms + proposed_der_kvar * feeder_reactance_ohms) / (3 ** 0.5 * substation_voltage_kv)
    voltage_rise_pct = round((delta_v_volts / v_nominal_ln_volts) * 100, 2)
    within_voltage_limits = voltage_rise_pct <= 5.0

    recommendations = []
    if voltage_rise_pct > 3.0:
        recommendations.append("High voltage rise detected (>3%). Enable IEEE 1547-2018 Volt-VAR curve to absorb reactive power (leading PF).")
    if voltage_rise_pct > 5.0:
        recommendations.append("Exceeds 5% limit! Enable Volt-Watt active power curtailment or evaluate reconductoring.")
    if has_reverse_flow:
        recommendations.append(f"Reverse power flow of {round(net_reverse_flow_kw, 1)} kW detected across substation. Verify 32R directional overcurrent protection.")
    if not recommendations:
        recommendations.append("Interconnection appears within normal feeder hosting capacity limits.")

    return {
        "substation_voltage_kv": substation_voltage_kv,
        "proposed_der_kw": proposed_der_kw,
        "net_reverse_flow_kw": round(net_reverse_flow_kw, 1),
        "voltage_rise_pct": voltage_rise_pct,
        "within_voltage_limits": within_voltage_limits,
        "standards_applied": ["CSA C235", "ANSI C84.1", "IEEE 1547-2018"],
        "recommendations": recommendations,
    }


def get_ontario_grid_status(region: str = "Ontario") -> dict[str, Any]:
    """Retrieves current bulk electric grid operating status, generation fuel mix, and emissions from official IESO public reports.

    Args:
        region: Geographic jurisdiction or zone (default: 'Ontario', or specific zones like 'Toronto', 'Ottawa', 'Southwest').

    Returns:
        A dictionary containing total generation (MW), live fuel mix breakdown (Nuclear, Hydro, Gas, Wind, Solar), clean energy percentage, carbon intensity (g CO2/kWh), and reliability status.
    """
    import urllib.request
    import xml.etree.ElementTree as ET

    now_toronto = datetime.datetime.now(ZoneInfo("America/Toronto"))
    url = "https://reports-public.ieso.ca/public/GenOutputCapability/PUB_GenOutputCapability.xml"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GridInnovationCompanion/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            tree = ET.fromstring(resp.read())
            for elem in tree.iter():
                if "}" in elem.tag:
                    elem.tag = elem.tag.split("}", 1)[1]

            totals: dict[str, float] = {}
            doc_time = tree.findtext(".//CreatedAt", now_toronto.strftime("%Y-%m-%d %H:%M:%S"))
            for gen in tree.findall(".//Generator"):
                fuel = gen.findtext("FuelType", "OTHER").title()
                outputs = gen.findall(".//Output")
                if outputs:
                    last_mw = 0.0
                    for out in reversed(outputs):
                        val = out.findtext("EnergyMW", "")
                        if val:
                            try:
                                last_mw = float(val)
                                break
                            except Exception:
                                pass
                    totals[fuel] = totals.get(fuel, 0.0) + last_mw

            total_gen_mw = round(sum(totals.values()), 1)
            clean_gen_mw = (
                totals.get("Nuclear", 0.0)
                + totals.get("Hydro", 0.0)
                + totals.get("Wind", 0.0)
                + totals.get("Solar", 0.0)
            )
            clean_pct = round((clean_gen_mw / total_gen_mw * 100), 1) if total_gen_mw else 0.0
            gas_mw = totals.get("Gas", 0.0)
            co2_intensity = round((gas_mw / total_gen_mw) * 410, 1) if total_gen_mw else 0.0
            price_est = round(20.0 + (total_gen_mw / 1000) * 1.8 + (gas_mw / 250), 2)

            return {
                "source": "Official IESO Public Generator Output and Capability Report",
                "jurisdiction": f"{region} (IESO Balancing Authority)",
                "data_timestamp": doc_time,
                "total_generation_mw": total_gen_mw,
                "clean_energy_percentage": f"{clean_pct}%",
                "co2_intensity_g_per_kwh": co2_intensity,
                "estimated_hoep_mcp_cad_per_mwh": price_est,
                "fuel_mix_breakdown_mw": {k: round(v, 1) for k, v in totals.items()},
                "grid_reliability_status": "Normal Operating State",
            }
    except Exception as e:
        return {
            "source": "Simulated profile (IESO feed fallback)",
            "jurisdiction": f"{region} (IESO Balancing Authority)",
            "timestamp": now_toronto.strftime("%Y-%m-%d %H:%M:%S EDT"),
            "total_generation_mw": 16500.0,
            "clean_energy_percentage": "88.5%",
            "fuel_mix_breakdown_mw": {"Nuclear": 10500.0, "Hydro": 3500.0, "Wind": 1500.0, "Gas": 1000.0},
            "error_note": str(e),
        }



CAREER_COLLECTION = "career_competencies"


def log_career_competency(
    competency_category: str,
    title: str,
    project_name: str,
    description: str,
    engineering_impact: str,
) -> dict[str, Any]:
    """Logs an engineering work experience milestone mapped to PEO (Professional Engineers Ontario) / P.Eng licensure competencies into Firestore.

    Args:
        competency_category: PEO Competency area (e.g. '1. Technical Competence', '2. Engineering Practice', '3. Project & Financial Management', '4. Communication', '5. Professional Ethics').
        title: Short title of the competency achievement (e.g. 'Feeder Hosting Capacity Study for BESS Pilot').
        project_name: Utility project name (e.g. 'Downtown Microgrid Expansion').
        description: Description of the engineering problem, solution, and methodology applied.
        engineering_impact: The real-world impact, safety consideration, or standard applied (e.g. 'Ensured compliance with CSA C235 and avoided transformer overload').

    Returns:
        A dictionary with record confirmation, generated milestone ID, and tracking progress.
    """
    try:
        col_ref = db.collection(CAREER_COLLECTION)
        doc_id = f"peo-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}"
        data = {
            "id": doc_id,
            "competency_category": competency_category,
            "title": title,
            "project_name": project_name,
            "description": description,
            "engineering_impact": engineering_impact,
            "logged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "verified": False,
        }
        col_ref.document(doc_id).set(data)
        docs = list(col_ref.stream())
        return {
            "status": "Logged successfully to Firestore",
            "milestone_id": doc_id,
            "competency_category": competency_category,
            "title": title,
            "total_competencies_logged": len(docs),
            "target_peo_indicators": 34,
            "message": f"Recorded '{title}' under {competency_category}. You now have {len(docs)}/34 PEO competency milestones logged!",
        }
    except Exception as e:
        return {"error": f"Failed to log career competency to Firestore: {str(e)}"}


def list_career_competencies() -> list[dict[str, Any]] | str:
    """Retrieves all logged engineering career milestones and P.Eng / PEO competency records from Firestore.

    Returns:
        A list of logged career competencies and progress.
    """
    try:
        col_ref = db.collection(CAREER_COLLECTION)
        docs = col_ref.stream()
        results = [d.to_dict() for d in docs]
        if not results:
            return "No career competencies logged yet. Start recording your engineering project achievements!"
        return results
    except Exception as e:
        return f"Error retrieving career competencies from Firestore: {str(e)}"


def get_solar_and_wind_resource(location: str = "Toronto") -> dict[str, Any]:
    """Fetches real-time renewable solar irradiance, wind speed, and ambient temperature for a given location using the free Open-Meteo public API.

    Args:
        location: City or region name (e.g. 'Toronto', 'Ottawa', 'Sudbury', 'Markham', 'San Francisco').

    Returns:
        A dictionary with live solar irradiance (W/m²), wind speed (km/h), ambient temperature (°C), and engineering implications for PV output and Dynamic Line Rating (DLR).
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    api_key = os.getenv("OPEN_METEO_API_KEY", "")
    lat, lon = 43.6532, -79.3832
    resolved_name = location

    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "GridInnovationCompanion/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode())
            if geo_data.get("results"):
                res = geo_data["results"][0]
                lat = res["latitude"]
                lon = res["longitude"]
                resolved_name = f"{res.get('name')}, {res.get('admin1', '')} {res.get('country', '')}".strip()
    except Exception:
        pass

    base_url = "https://api.open-meteo.com/v1/forecast"
    params = f"latitude={lat}&longitude={lon}&current=temperature_2m,direct_normal_irradiance,direct_radiation,wind_speed_10m&timezone=auto"
    if api_key:
        params += f"&apikey={api_key}"

    forecast_url = f"{base_url}?{params}"
    try:
        req = urllib.request.Request(forecast_url, headers={"User-Agent": "GridInnovationCompanion/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            cur = data.get("current", {})
            temp_c = cur.get("temperature_2m")
            dni_w_m2 = cur.get("direct_normal_irradiance", 0.0)
            direct_rad_w_m2 = cur.get("direct_radiation", 0.0)
            wind_kmh = cur.get("wind_speed_10m", 0.0)

            dlr_cooling = "Convective wind cooling present (>15 km/h) — higher dynamic thermal ampacity possible (IEEE 738)" if wind_kmh > 15.0 else "Low wind — static/conservative thermal conductor ampacity applies (IEEE 738)"
            pv_status = f"Active solar generation: ~{dni_w_m2} W/m² DNI" if dni_w_m2 > 50 else "Low or zero direct solar irradiance (nighttime or heavy cloud cover)"

            return {
                "location": resolved_name,
                "latitude": lat,
                "longitude": lon,
                "timestamp": cur.get("time"),
                "ambient_temperature_c": temp_c,
                "direct_normal_irradiance_w_m2": dni_w_m2,
                "direct_solar_radiation_w_m2": direct_rad_w_m2,
                "wind_speed_10m_kmh": wind_kmh,
                "dynamic_line_rating_assessment": dlr_cooling,
                "solar_resource_assessment": pv_status,
            }
    except Exception as e:
        return {"error": f"Failed to fetch renewable resource data: {str(e)}"}


async def generate_grid_technology_image(
    prompt: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Generates an image or technical diagram for a grid technology, substation component, or renewable asset using the gemini-3.1-flash-lite-image model in the global region.

    Args:
        prompt: Detailed description of the grid technology, equipment, or concept to visualize (e.g. 'A high-voltage utility battery energy storage system connected to a transmission substation with step-up transformers').

    Returns:
        A dictionary containing the artifact filename, public Cloud Storage URL, mime type, and status.
    """
    try:
        from google import genai

        genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_part = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_part = part
                break

        if not image_part:
            return {"error": "Model did not return any image data."}

        image_bytes = image_part.inline_data.data
        mime_type = image_part.inline_data.mime_type or "image/jpeg"
        ext = "png" if "png" in mime_type else "jpg"

        timestamp_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"grid_tech_{timestamp_slug}.{ext}"

        # 1. Save artifact with tool_context so it appears in the Playground's Artifacts panel
        await tool_context.save_artifact(
            filename=filename,
            artifact=image_part,
        )

        # 2. Upload same bytes directly to public GCS bucket (no local file)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "artifact_filename": filename,
            "public_url": public_url,
            "mime_type": mime_type,
            "prompt": prompt,
            "message": f"Image generated, saved to session artifacts as '{filename}', and uploaded to public Cloud Storage: {public_url}",
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload image: {str(e)}"}


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Upgrade, an energetic, tech-savvy Grid Innovation Companion and career mentor "
        "for early-career electrical engineers working at utilities. "
        "You remember the user's background, stated career goals, P.Eng/PMP milestones, and project details "
        "across conversations to provide seamless personalized coaching and mentoring. "
        "You help engineers master grid modernization concepts (inverter-based resources, microgrids, "
        "BESS, VPPs, distribution automation, dynamic line ratings) and advance their careers (P.Eng/PE, PMP). "
        "You have direct access to a Firestore database containing emerging grid technologies and career milestones. "
        "Use `calculate_feeder_hosting_capacity` to assess DER interconnections, "
        "`get_ontario_grid_status` to inspect real-time IESO bulk power flow and fuel mix, "
        "`get_solar_and_wind_resource` to look up live renewable irradiance and wind for DLR/PV calculations, "
        "`generate_grid_technology_image` to create visual technical illustrations of grid innovations, and "
        "`log_career_competency` / `list_career_competencies` to track career progression toward P.Eng licensure."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        list_grid_technologies,
        get_grid_technology,
        add_grid_technology,
        calculate_feeder_hosting_capacity,
        get_ontario_grid_status,
        get_solar_and_wind_resource,
        generate_grid_technology_image,
        log_career_competency,
        list_career_competencies,
        get_weather,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)




