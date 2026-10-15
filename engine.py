"""Lynq NTN-Pulse — engine.py (Physical Dataset Generator & Orbital Simulator).

Physically generates and saves the 4 required Phase 2 files on disk:
1. simulation_results_v2.csv
2. scenario_summary_v2.csv
3. orbit_tracks_v2.csv
4. model_metadata_v2.json

Run:
    python engine.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent

TERMINALS = {
    "North Sea Wind Farm": {"lat": 56.35, "lon": 3.55, "sector": "Central North Sea"},
    "Energy Platform Alpha": {"lat": 58.20, "lon": 1.20, "sector": "Northern Offshore Corridor"},
}

GATEWAYS = {
    "Blocked / Unauthorized GW": {"lat": 51.75, "lon": 4.10},
    "Authorized EU / Luxembourg GW": {"lat": 49.61, "lon": 6.13},
}

FLEET_SIZES = [12, 30, 48]
ARCHITECTURES = ["regenerative", "functional_split", "bent_pipe"]
ISL_TOPOLOGIES = ["rf_intra_plane", "optical_cross_plane", "hybrid"]
TIME_STEPS = list(range(0, 95, 5))  # 0 to 90 minutes in 5-min steps


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def generate_orbit_tracks() -> pd.DataFrame:
    """Generates Walker-Delta LEO orbital tracks for all 12, 30, and 48 satellites."""
    rows = []
    for fleet in FLEET_SIZES:
        planes = 3 if fleet in (12, 30) else 4
        sats_per_plane = fleet // planes
        for p in range(planes):
            raan_lon_offset = -16.0 + p * (28.0 / max(1, planes - 1))
            for s in range(sats_per_plane):
                sat_idx = p * sats_per_plane + s + 1
                sat_name = f"LYNQ-{sat_idx:02d}"
                mean_anomaly_deg = s * (360.0 / sats_per_plane) + p * 18.0
                for t in TIME_STEPS:
                    # 95-minute LEO orbital period (~550 km altitude, 10 deg min elevation)
                    theta = math.radians(mean_anomaly_deg + t * 3.8)
                    lat = 55.5 + 13.5 * math.sin(theta)
                    lon = raan_lon_offset + 18.0 * math.cos(theta) + (t * 0.22)
                    rows.append(
                        {
                            "fleet_size": fleet,
                            "plane": p + 1,
                            "satellite": sat_name,
                            "time_min": t,
                            "lat": round(lat, 3),
                            "lon": round(lon, 3),
                        }
                    )
    return pd.DataFrame(rows)


def generate_simulation_results(tracks_df: pd.DataFrame) -> pd.DataFrame:
    """Computes visibility, dynamic serving/relay satellites, link budgets, and latency."""
    rows = []
    auth_gw = GATEWAYS["Authorized EU / Luxembourg GW"]

    # Footprint radius at 550 km altitude and 10-deg minimum elevation (~1,500 km radius / ~3,000 km diameter)
    footprint_radius_km = 1350.0

    for fleet in FLEET_SIZES:
        fleet_tracks = tracks_df[tracks_df["fleet_size"] == fleet]
        for arch in ARCHITECTURES:
            for isl in ISL_TOPOLOGIES:
                for term_name, term_coords in TERMINALS.items():
                    t_lat, t_lon = term_coords["lat"], term_coords["lon"]
                    queue_mb = 8.0

                    for t in TIME_STEPS:
                        step_sats = fleet_tracks[fleet_tracks["time_min"] == t].copy()
                        step_sats["dist_term_km"] = step_sats.apply(
                            lambda r: _haversine_km(t_lat, t_lon, r["lat"], r["lon"]), axis=1
                        )
                        step_sats["dist_auth_km"] = step_sats.apply(
                            lambda r: _haversine_km(auth_gw["lat"], auth_gw["lon"], r["lat"], r["lon"]), axis=1
                        )

                        # Nearest satellite to the offshore terminal is the Serving Satellite
                        serving = step_sats.sort_values("dist_term_km").iloc[0]
                        sat_id = str(serving["satellite"])
                        sat_lat = float(serving["lat"])
                        sat_lon = float(serving["lon"])
                        dist_term = float(serving["dist_term_km"])
                        dist_auth_direct = float(serving["dist_auth_km"])

                        # Nearest distinct satellite to the Authorized Luxembourg Gateway is the Relay Satellite
                        other_sats = step_sats[step_sats["satellite"] != sat_id].sort_values("dist_auth_km")
                        relay = other_sats.iloc[0]
                        relay_id = str(relay["satellite"])
                        relay_lat = float(relay["lat"])
                        relay_lon = float(relay["lon"])
                        dist_isl = _haversine_km(sat_lat, sat_lon, relay_lat, relay_lon)

                        # Visibility determination based on fleet density & orbital geometry
                        if fleet == 12:
                            term_vis = bool(dist_term <= footprint_radius_km and (t not in [15, 45, 75]))
                            auth_vis = bool(dist_auth_direct <= 1150.0 and (t in [0, 20, 25, 50, 70, 90]))
                            base_wait = 26.0
                        elif fleet == 30:
                            term_vis = bool(dist_term <= footprint_radius_km and (t != 45))
                            auth_vis = bool(dist_auth_direct <= 1250.0 or (t % 15 == 0))
                            base_wait = 11.0
                        else:  # 48 LEO Gen-2 (continuous multi-plane coverage)
                            term_vis = True
                            auth_vis = bool(dist_auth_direct <= 1300.0 or (t % 10 == 0))
                            base_wait = 4.0

                        # Route availability by payload architecture & ISL topology
                        if arch == "bent_pipe":
                            # Bent-pipe requires simultaneous line-of-sight to terminal AND authorized feeder GW
                            route_avail = bool(term_vis and auth_vis)
                        else:
                            if isl == "hybrid":
                                route_avail = bool(term_vis)
                            elif isl == "optical_cross_plane":
                                route_avail = bool(term_vis and (fleet >= 30 or t != 35))
                            else:  # rf_intra_plane
                                route_avail = bool(term_vis and (fleet == 48 or t not in [20, 65]))

                        # Propagation + Processing + Switching Latency (ms)
                        if route_avail:
                            sl_rtt_ms = (dist_term + 550.0) / 300.0 * 4.2
                            isl_prop_ms = (dist_isl / 300.0) * 3.5
                            if arch == "bent_pipe":
                                proc_ms = 92.0
                                isl_hop_ms = 0.0
                            elif arch == "functional_split":
                                proc_ms = 66.0  # DU onboard, CU on ground adds fronthaul serialization
                                isl_hop_ms = 18.0 if isl == "rf_intra_plane" else (9.0 if isl == "optical_cross_plane" else 13.0)
                            else:  # Full Regenerative gNB onboard
                                proc_ms = 56.0
                                isl_hop_ms = 16.0 if isl == "rf_intra_plane" else (7.0 if isl == "optical_cross_plane" else 11.0)

                            fleet_bonus = 0.0 if fleet == 12 else (-6.0 if fleet == 30 else -11.0)
                            crit_latency = round(max(45.0, proc_ms + sl_rtt_ms + isl_prop_ms + isl_hop_ms + fleet_bonus), 1)
                        else:
                            crit_latency = None

                        # Store-and-forward onboard buffer queue dynamics (64 MB max 6U buffer)
                        inflow_mb = 3.2 if "Wind" in term_name else 4.1
                        drain_mb = (4.5 if auth_vis else (2.6 if route_avail and isl != "rf_intra_plane" else 1.2)) * (
                            1.0 if fleet == 12 else (1.35 if fleet == 30 else 1.7)
                        )
                        queue_mb = round(min(62.0, max(4.0, queue_mb + inflow_mb - drain_mb)), 1)

                        next_wait = round(max(1.5, base_wait - (t % 20) * 0.45), 1)
                        reg_delivery = round(next_wait + (4.5 if isl == "rf_intra_plane" else 2.0), 1)
                        handover_sec = 3.4 if isl == "rf_intra_plane" else (1.8 if isl == "optical_cross_plane" else 2.4)
                        snr_db = round(14.5 - (dist_term / 450.0) + (1.8 if fleet >= 30 else 0.0), 1)

                        rows.append(
                            {
                                "fleet_size": fleet,
                                "architecture": arch,
                                "isl_topology": isl,
                                "terminal": term_name,
                                "time_min": t,
                                "satellite": sat_id,
                                "sat_lat": sat_lat,
                                "sat_lon": sat_lon,
                                "relay_satellite": relay_id,
                                "relay_lat": relay_lat,
                                "relay_lon": relay_lon,
                                "dist_term_km": round(dist_term, 1),
                                "isl_distance_km": round(dist_isl, 1),
                                "link_snr_db": snr_db,
                                "terminal_visible": term_vis,
                                "authorized_visible": auth_vis,
                                "route_available": route_avail,
                                "critical_latency_ms": crit_latency,
                                "regular_delivery_min": reg_delivery,
                                "queue_depth_mb": queue_mb,
                                "next_pass_wait_min": next_wait,
                                "handover_transfer_s": handover_sec,
                            }
                        )
    return pd.DataFrame(rows)


def generate_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    return (
        results_df.groupby(["fleet_size", "architecture", "isl_topology"], as_index=False)
        .agg(
            availability_pct=("route_available", lambda s: round(100.0 * s.mean(), 1)),
            mean_critical_latency_ms=(
                "critical_latency_ms",
                lambda s: round(s.dropna().mean(), 1) if not s.dropna().empty else None,
            ),
            mean_store_forward_min=("regular_delivery_min", lambda s: round(s.mean(), 1)),
            max_queue_mb=("queue_depth_mb", "max"),
            handover_transfer_s=("handover_transfer_s", "first"),
        )
    )


def generate_metadata() -> dict:
    return {
        "project": "Lynq NTN-Pulse",
        "model_status": "Illustrative scenario simulation; not flight-validated",
        "model_assumptions": [
            "Parametric orbital tracks are used for demonstration purposes.",
            "Latency, ISL rate, SWaP and buffer values are configurable assumptions.",
            "Gateway authorization and data-sovereignty routing are scenario assumptions.",
            "Final values require validation with OQ payload and regulatory data.",
        ],
        "challenge": "NeoSpace Europe 2026 — OQ Technology AnyPoint-NTN",
        "hpc_environment": "MeluXina EuroHPC (Project p201621)",
        "orbital_shell": {"altitude_km": 550, "min_elevation_deg": 10, "footprint_diameter_km": 3000},
        "constellation_tiers": {
            "12": "Current demonstrator baseline: 12 LEO satellites; mission composition to be confirmed with OQ",
            "30": "Planned expansion (3 planes x 10 satellites, ~2.5x smaller revisit gap)",
            "48": "Gen-2 target constellation (4 planes x 12 satellites, near-continuous coverage)",
        },
        "payload_architectures": {
            "regenerative": "Full 3GPP Rel-17/18/19 gNB onboard satellite",
            "functional_split": "3GPP CU/DU Split (DU onboard satellite, CU at sovereign ground gateway)",
            "bent_pipe": "Transparent RF repeater requiring simultaneous gateway line-of-sight",
        },
        "isl_link_budget": {
            "rf_intra_plane": {"rate_mbps": 4.0, "swap_w": 8.0, "license": "ITU / ILR Spectrum License Required"},
            "optical_cross_plane": {"rate_mbps": 100.0, "swap_w": 22.0, "license": "Optical laser link; export-control and national authorization review required"},
            "hybrid": {"rate_mbps": 15.0, "swap_w": 14.0, "license": "RF Intra-plane + Optical Cross-plane Relay"},
        },
        "business_case": {"annual_opex_eur": 9000000, "breakeven_offshore_assets": 75000, "subscription_eur_yr": 120},
    }


def main() -> None:
    print("🚀 Running Lynq NTN-Pulse Orbital & Policy Engine...")
    tracks_df = generate_orbit_tracks()
    results_df = generate_simulation_results(tracks_df)
    summary_df = generate_summary(results_df)
    metadata = generate_metadata()

    tracks_df.to_csv(ROOT / "orbit_tracks_v2.csv", index=False)
    results_df.to_csv(ROOT / "simulation_results_v2.csv", index=False)
    summary_df.to_csv(ROOT / "scenario_summary_v2.csv", index=False)
    with open(ROOT / "model_metadata_v2.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("✅ Physical dataset files successfully written to disk:")
    print(f"   1. {ROOT / 'simulation_results_v2.csv'} ({len(results_df)} rows)")
    print(f"   2. {ROOT / 'scenario_summary_v2.csv'} ({len(summary_df)} rows)")
    print(f"   3. {ROOT / 'orbit_tracks_v2.csv'} ({len(tracks_df)} rows)")
    print(f"   4. {ROOT / 'model_metadata_v2.json'}")


if __name__ == "__main__":
    main()
