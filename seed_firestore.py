"""Seed Firestore collection for Grid Innovation Companion (Upgrade)."""

from google.cloud import firestore

# Hardcoded project ID as required (do NOT use GOOGLE_CLOUD_PROJECT or google.auth.default())
PROJECT_ID = "qwiklabs-gcp-04-db22d601027d"
COLLECTION_NAME = "grid_technologies"

SEED_DATA = [
    {
        "id": "grid-forming-inverters",
        "name": "Grid-Forming Inverters (GFM)",
        "category": "Inverter-Based Resources (IBR)",
        "trl": 8,
        "summary": "Voltage source inverters that establish frequency and voltage references without relying on synchronous machines.",
        "primary_use_case": "Synthetic inertia, weak grid stabilization, and microgrid black-start capability.",
        "relevant_standards": ["IEEE 2800-2022", "IEEE 1547-2018", "NERC Reliability Guideline IBR"],
        "status": "Pilot Testing",
        "engineering_notes": "Essential for Ontario circuits with high inverter-based solar/wind penetration displacing synchronous inertia."
    },
    {
        "id": "bess-long-duration",
        "name": "Long-Duration Battery Energy Storage (BESS)",
        "category": "Energy Storage",
        "trl": 9,
        "summary": "Multi-hour 4h-10h utility-scale lithium iron phosphate (LFP) or flow battery storage system.",
        "primary_use_case": "Feeder peak shaving, transmission congestion relief, and capacity arbitrage.",
        "relevant_standards": ["UL 9540A", "NFPA 855", "IEEE 2030.2.1"],
        "status": "Commercial Deployment",
        "engineering_notes": "IESO Expedited Long-Term RFP (E-LT1) procurement focus for Ontario clean energy storage."
    },
    {
        "id": "virtual-power-plants",
        "name": "Virtual Power Plants (VPP) & DERMS",
        "category": "Distributed Energy Resources",
        "trl": 8,
        "summary": "Cloud-orchestrated aggregation of residential batteries, smart thermostats, and EV chargers dispatching flexible capacity.",
        "primary_use_case": "Non-wires alternatives (NWA) for substation deferral and wholesale ancillary market services.",
        "relevant_standards": ["IEEE 2030.5", "OpenADR 2.0b", "FERC Order 2222"],
        "status": "Pilot Testing",
        "engineering_notes": "Aligns with Ontario Energy Board (OEB) FEB innovation sandboxes and municipal utility DERMS rollouts."
    },
    {
        "id": "dynamic-line-rating",
        "name": "Dynamic Line Rating (DLR)",
        "category": "Transmission & Distribution Optimization",
        "trl": 8,
        "summary": "Real-time overhead line capacity sensing based on ambient temperature, solar radiation, and wind cooling.",
        "primary_use_case": "Unlocking 10-40% hidden transmission/sub-transmission capacity during peak wind generation.",
        "relevant_standards": ["IEEE 738-2012", "CIGRE TB 299"],
        "status": "Pilot Testing",
        "engineering_notes": "Allows integrating renewable generation without expensive reconductoring or pole replacements."
    },
    {
        "id": "smart-ev-fleet-v2g",
        "name": "Vehicle-to-Grid (V2G) Fleet Charging",
        "category": "Electrification & Mobility",
        "trl": 7,
        "summary": "Bidirectional DC fast-charging infrastructure for municipal electric bus and commercial fleet depots.",
        "primary_use_case": "Peak demand reduction at fleet depots and localized distribution feeder support during heatwaves.",
        "relevant_standards": ["ISO 15118-20", "SAE J3072", "IEEE 1547-2018"],
        "status": "Research & Demonstration",
        "engineering_notes": "Critical for transit electrification in urban Ontario centers like Toronto and Ottawa."
    }
]

def seed():
    print(f"Connecting to Firestore with hardcoded project ID: {PROJECT_ID}")
    db = firestore.Client(project=PROJECT_ID)
    batch = db.batch()
    col_ref = db.collection(COLLECTION_NAME)

    for item in SEED_DATA:
        doc_ref = col_ref.document(item["id"])
        batch.set(doc_ref, item)
        print(f"  + Queued: {item['id']} ({item['name']})")

    batch.commit()
    print(f"✅ Successfully seeded {len(SEED_DATA)} items into '{COLLECTION_NAME}' collection!")

if __name__ == "__main__":
    seed()
