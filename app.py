"""Lynq NTN-Pulse v3 (Enhanced) — space-tech digital-twin dashboard.

Incorporates OQ Technology technical feedback:
- 3GPP Regenerative options: Full gNB vs Functional Split (DU onboard / CU ground)
- RF vs Optical ISL Link Budget, Duty Cycle & Regulatory Spectrum (ILR) trade-offs
- Multi-second Store-and-Forward Handover Context Transfer
- MeluXina HPC (Project p201621) simulation provenance

Run after engine_v2.py:
    python engine_v2.py
    python -m streamlit run app_v3.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent

TERMINALS = {
    "North Sea Wind Farm": {"lat": 56.35, "lon": 3.55, "kind": "Offshore wind terminal"},
    "Energy Platform Alpha": {"lat": 58.20, "lon": 1.20, "kind": "Remote energy platform"},
}

GATEWAYS = {
    "Blocked / Unauthorized GW": {"lat": 51.75, "lon": 4.10},
    "Authorized EU / Luxembourg GW": {"lat": 49.61, "lon": 6.13},
}

TOPOLOGY_LABELS = {
    "RF intra-plane (S-band / Licensed)": "rf_intra_plane",
    "Optical cross-plane (Laser)": "optical_cross_plane",
    "Hybrid RF + Optical ISL": "hybrid",
}

ISL_SPECS = {
    "rf_intra_plane": {
        "rate": "2–5 Mbps",
        "power": "Low SWaP (~8 W, 35% duty cycle)",
        "licensing": "Requires ITU / National Spectrum License (e.g., ILR)",
        "handover": "3.5 s (Store-and-Forward context transfer)",
        "latency_delta": 12,
    },
    "optical_cross_plane": {
        "rate": "100+ Mbps",
        "power": "Higher SWaP (~22 W, precision PAT pointing)",
        "licensing": "License-free optical spectrum",
        "handover": "1.8 s (Fast inter-plane context sync)",
        "latency_delta": -8,
    },
    "hybrid
