"""Lynq NTN-Pulse — engine_v2.py (Updated post-OQ Technology Meeting).

Generates deterministic digital-twin datasets incorporating OQ engineering feedback:
1. Constellation sizes: 12 (Baseline), 30 (Intermediate), 48 (Gen-2 Target)
2. 3GPP Architectures: Regenerative (Full gNB), Functional Split (DU/CU), Bent-pipe
3. ISL Topologies: RF intra-plane (licensed), Optical cross-plane, Hybrid RF+Optical
4. Realistic Store-and-Forward buffer dynamics (64 MB 6U constraint) & multi-second handover

Outputs created automatically:
- simulation_results_v2.csv
- scenario_summary_v2.csv
- orbit_tracks_v2.csv
- model_metadata_v2.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent

TERMINALS = {
    "North Sea Wind Farm": {"lat": 56.35, "lon": 3.55},
    "Energy Platform Alpha": {"lat": 58.20, "lon": 1.20},
}

AUTHORIZED_GW = {"name": "Authorized EU / Luxembourg GW", "lat": 49.61, "lon": 6.13}
BLOCKED_GW = {"name": "Blocked / Unauthorized GW", "lat": 51.75, "lon": 4.10}

FLEET_SIZES = [12, 30, 48]
ARCHITECTURES = ["regenerative", "functional_split", "bent_pipe"]
ISL_TOPOLOGIES = ["rf_intra_plane", "optical_cross_plane", "hybrid"]
TIME_STEPS = list(range(0, 95, 5))  # 0 to 90 minutes in 5-min steps


def generate_orbit_tracks() -> pd.DataFrame:
    rows = []
    for fleet in FLEET_SIZES:
        num_displayed_sats = 6 if fleet == 12 else (10 if fleet == 30 else 14)
        for sat_idx in range(1, num_displayed_sats + 1):
            sat_name = f"LYNQ-{sat_idx:02d}"
            phase_offset = (sat_idx - 1) * (180.0 / num_displayed_sats)
            lon_offset = (sat_idx - 1) * (45.0 / num_displayed_sats) - 18.0
            for t in TIME_STEPS:
                angle = math.radians((t * 4.0) + phase_offset)
                lat = 55.0 + 14.5 * math.sin(angle)
                lon = lon_offset + (t * 0.42) + 8.0 * math.cos(angle * 0.7)
                rows.append(
                    {
                        "fleet_size": fleet,
                        "satellite": sat_name,
                        "time_min": t,
                        "lat": round(lat, 3),
                        "lon": round(lon, 3),
                    }
                )
    return pd.DataFrame(rows)


def generate_simulation_results() -> pd.DataFrame:
    rows = []
    for fleet in FLEET_SIZES:
        for arch in ARCHITECTURES:
            for isl in ISL_TOPOLOGIES:
                for term_name, term_coords in TERMINALS.items():
                    for t in TIME_STEPS:
                        # Serving satellite motion around North Sea
                        angle = math.radians(t * 4.0 + (5 if fleet >= 30 else 0))
                        sat_lat = round(term_coords["lat"] + 4.8 * math.sin(angle), 2)
                        sat_lon = round(term_coords["lon"] + 6.2 * math.cos(angle), 2)
                        sat_id = f"LYNQ-{((t // 15 + (0 if fleet == 12 else 2)) % 8) + 1:02d}"

                        # Visibility & revisit window scaling by fleet size (12 vs 30 vs 48 Gen-2)
                        if fleet == 12:
                            term_vis = (t % 25) != 10 and (t % 30) != 15
                            auth_vis = (t % 20) == 0 or (t in [25, 50, 75])
                            base_wait = 28.0
                        elif fleet == 30:
                            term_vis = (t % 35) != 15
                            auth_vis = (t % 15) == 0 or (t in [20, 25, 40, 55, 70, 85])
                            base_wait = 14.0
                        else:  # 48 satellites (Gen-2 near-continuous coverage)
                            term_vis = True
                            auth_vis = (t % 10) == 0 or (t in [15, 25, 35, 45, 65, 75, 85])
                            base_wait = 6.0

                        # Route availability logic
                        if arch == "bent_pipe":
                            # Bent-pipe needs simultaneous terminal + authorized feeder visibility
                            route_avail = bool(term_vis and auth_vis)
                        else:
                            # Regenerative & Functional Split can route over ISL whenever terminal is visible
                            if isl == "hybrid":
                                route_avail = bool(term_vis)
                            elif isl == "optical_cross_plane":
                                route_avail = bool(term_vis and (fleet >= 30 or t % 15 != 5))
                            else:  # rf_intra_plane
                                route_avail = bool(term_vis and (fleet == 48 or t % 20 != 10))

                        # Latency calculation (ms) including ISL type, 3GPP split & handover context
                        if route_avail:
                            base_lat = 88.0 if fleet == 12 else (76.0 if fleet == 30 else 68.0)
                            isl_mod = 12.0 if isl == "rf_intra_plane" else (-6.0 if isl == "optical_cross_plane" else 0.0)
                            arch_mod = 0.0 if arch == "regenerative" else (7.0 if arch == "functional_split" else 22.0)
                            jitter = (t % 15) * 0.4
                            crit_latency = round(base_lat + isl_mod + arch_mod + jitter, 1)
                        else:
                            crit_latency = None

                        # Store-and-forward queue depth (64 MB max 6U buffer) & delivery wait
                        queue_