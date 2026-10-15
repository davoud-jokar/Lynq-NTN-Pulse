# 🛰️ Lynq NTN-Pulse

**A jurisdiction-aware digital twin and policy engine for regenerative 3GPP 5G NR-NTN constellations**

NeoSpace Europe 2026 — OQ Technology AnyPoint-NTN Challenge

## Overview

Lynq NTN-Pulse is an illustrative digital-twin demonstrator for offshore energy corridors in the North Sea.

It evaluates how a regenerative onboard payload can prioritise industrial traffic when a local gateway is unavailable, blocked or not permitted, subject to an authorised feeder or inter-satellite path and applicable jurisdictional controls.

**Winning message:**
Lynq keeps critical offshore signals moving when the local gateway cannot.

## Main Capabilities

- Parametric comparison of 12, 30 and 48 LEO satellite fleets.
- Comparison of regenerative full-gNB, CU/DU functional split and transparent bent-pipe architectures.
- Comparison of RF, optical and hybrid ISL topologies.
- Critical alarm prioritisation through low-latency ISL routing.
- Bulk telemetry using an illustrative store-and-forward buffer.
- Scenario-level policy checks for gateway authorisation, spectrum assumptions and data residency.
- 2D North Sea map and orthographic globe visualisation.
- Interactive orbital pass, latency and buffer-queue charts.

## Important Model Note

This is an illustrative scenario simulation for Phase 2 demonstration.

Orbital tracks, latency, ISL rates, SWaP values, buffer size, gateway authorisation and business-case values are configurable assumptions. They are not flight-validated measurements or formal regulatory certification.

Final payload, spectrum, gateway and compliance parameters require validation with OQ Technology and the relevant authorities.

## Local Installation

```bash
pip install -r requirements.txt
python engine.py
streamlit run app.py
```

The application can also use the committed CSV and JSON datasets directly.

## Main Files

- `app.py` — Streamlit dashboard and visual policy engine.
- `engine.py` — Parametric orbital and traffic simulation engine.
- `simulation_results_v2.csv` — Scenario-level routing and latency results.
- `scenario_summary_v2.csv` — Aggregated availability and performance results.
- `orbit_tracks_v2.csv` — Parametric satellite tracks.
- `model_metadata_v2.json` — Model configuration and assumptions.
- `requirements.txt` — Python dependencies.

## HPC Context

The project is designed for execution and extension on the MeluXina EuroHPC environment under the NeoSpace Challenge.

HPC execution results and provenance should be documented separately from the illustrative model assumptions.
