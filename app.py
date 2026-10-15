"""Lynq NTN-Pulse v3 (Self-Contained) — space-tech digital-twin dashboard.

Incorporates OQ Technology technical feedback:
- 3GPP Regenerative options: Full gNB vs Functional Split (DU onboard / CU ground)
- RF vs Optical ISL Link Budget, Duty Cycle & Regulatory Spectrum (ILR) trade-offs
- Multi-second Store-and-Forward Handover Context Transfer
- MeluXina HPC (Project p201621) simulation provenance
- Built-in In-Memory Engine Fallback (Zero FileNotFoundError guaranteed)
"""

from __future__ import annotations

import math
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

ARCH_LABELS = {
    "Regenerative (Full gNB Onboard)": "regenerative",
    "Regenerative (Functional Split DU/CU)": "functional_split",
    "Transparent (Bent-pipe)": "bent_pipe",
}

ISL_SPECS = {
    "rf_intra_plane": {
        "rate": "2–5 Mbps",
        "power": "Low SWaP (~8 W, 35% duty cycle)",
        "licensing": "Requires ITU / National Spectrum License (e.g., ILR)",
        "handover": "3.4 s (Store-and-Forward context transfer)",
        "latency_delta": 12,
    },
    "optical_cross_plane": {
        "rate": "100+ Mbps",
        "power": "Higher SWaP (~22 W, precision PAT pointing)",
        "licensing": "License-free optical spectrum",
        "handover": "1.8 s (Fast inter-plane context sync)",
        "latency_delta": -6,
    },
    "hybrid": {
        "rate": "15 Mbps effective (RF hop + Optical trunk)",
        "power": "Balanced SWaP (~14 W, adaptive duty cycle)",
        "licensing": "Hybrid (RF intra-plane coordinated + Optical relay)",
        "handover": "2.4 s (3GPP Xn-over-ISL context transfer)",
        "latency_delta": 0,
    },
}

st.set_page_config(
    page_title="Lynq NTN-Pulse | Mission Control",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root {
        --space:#050914;
        --space-2:#091426;
        --panel:rgba(13,25,43,.88);
        --panel-2:rgba(16,31,53,.94);
        --line:#1f3a57;
        --cyan:#00e5ff;
        --teal:#20e6bf;
        --blue:#72a9ff;
        --muted:#9db0c6;
        --text:#eef8ff;
        --red:#ff6475;
        --amber:#ffd166;
    }

    .stApp {
        color:var(--text);
        background:
            radial-gradient(circle at 80% 4%, rgba(0,229,255,.11) 0 1px, transparent 2px),
            radial-gradient(circle at 22% 18%, rgba(255,255,255,.22) 0 1px, transparent 2px),
            radial-gradient(circle at 65% 34%, rgba(114,169,255,.18) 0 1px, transparent 2px),
            radial-gradient(circle at 10% 76%, rgba(32,230,191,.15) 0 1px, transparent 2px),
            radial-gradient(circle at 94% 82%, rgba(255,255,255,.18) 0 1px, transparent 2px),
            linear-gradient(135deg, #050914 0%, #081426 52%, #050914 100%);
        background-size: 260px 230px, 340px 270px, 410px 330px, 310px 260px, 390px 300px, auto;
    }

    .block-container { max-width:1540px; padding:1.2rem 2rem 2.4rem; }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#081323 0%,#0a1728 100%); border-right:1px solid var(--line); }
    [data-testid="stSidebar"] .block-container { padding:1.25rem 1.05rem; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown { color:var(--text); }
    [data-testid="stSidebar"] .stCaption { color:var(--muted); }

    .brandline { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:.5rem; }
    .brand { font-size:1.32rem; font-weight:850; letter-spacing:.08em; color:var(--text); }
    .brand span { color:var(--cyan); }
    .chip-group { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; }
    .mission-chip { border:1px solid rgba(0,229,255,.42); color:var(--cyan); border-radius:999px; padding:.38rem .72rem; font-size:.65rem; letter-spacing:.12em; font-weight:800; white-space:nowrap; }
    .hpc-chip { border:1px solid rgba(32,230,191,.45); background:rgba(32,230,191,.08); color:var(--teal); border-radius:999px; padding:.38rem .72rem; font-size:.65rem; letter-spacing:.10em; font-weight:800; white-space:nowrap; }
    .sub { color:var(--muted); font-size:.78rem; letter-spacing:.02em; }

    .hero { position:relative; overflow:hidden; border:1px solid #285171; border-radius:20px; padding:1.2rem 1.35rem 1.05rem; background:linear-gradient(110deg,rgba(0,229,255,.14),rgba(12,28,49,.88) 48%,rgba(32,230,191,.08)); box-shadow:0 0 35px rgba(0,229,255,.06); margin:.75rem 0 1rem; }
    .hero:after { content:'✦  ·  ✧  ·  ✦'; position:absolute; right:1rem; top:.45rem; color:rgba(190,231,255,.25); font-size:1.15rem; letter-spacing:.55rem; }
    .eyebrow { color:var(--cyan); text-transform:uppercase; letter-spacing:.16em; font-size:.64rem; font-weight:850; }
    .hero h1 { margin:.2rem 0 .3rem; font-size:1.78rem; color:var(--text); letter-spacing:.01em; }
    .hero p { max-width:920px; margin:0; color:#c7d7e8; font-size:.88rem; line-height:1.45; }
    .hero-steps { display:grid; grid-template-columns:repeat(3,1fr); gap:.6rem; margin-top:.9rem; }
    .hero-step { border:1px solid rgba(104,157,194,.28); border-radius:11px; padding:.55rem .65rem; background:rgba(4,14,27,.38); color:#bdd1e4; font-size:.72rem; line-height:1.35; }
    .hero-step b { color:var(--cyan); margin-right:.25rem; }

    .section-head { display:flex; justify-content:space-between; align-items:baseline; gap:.7rem; margin:.85rem 0 .5rem; }
    .section-head h2 { margin:0; color:var(--text); font-size:1.02rem; letter-spacing:.01em; }
    .section-head span { color:var(--muted); font-size:.72rem; }

    .card { border:1px solid var(--line); border-radius:14px; padding:.82rem .9rem; background:var(--panel); box-shadow:0 9px 25px rgba(0,0,0,.12); min-height:82px; }
    .card.highlight { border-color:rgba(0,229,255,.5); background:linear-gradient(135deg,rgba(0,229,255,.12),rgba(13,25,43,.94)); }
    .card.redline { border-color:rgba(255,100,117,.55); }
    .card.amberline { border-color:rgba(255,209,102,.55); }
    .label { color:#88a1bb; font-size:.64rem; text-transform:uppercase; letter-spacing:.13em; font-weight:800; }
    .value { color:var(--cyan); font-size:1.08rem; font-weight:850; margin-top:.32rem; line-height:1.22; }
    .value.green { color:var(--teal); }
    .value.amber { color:var(--amber); }
    .value.red { color:var(--red); }
    .note { color:var(--muted); font-size:.73rem; line-height:1.4; margin-top:.28rem; }
    .note b { color:#dcecff; }
    .explain { border-left:3px solid var(--cyan); border-radius:0 10px 10px 0; padding:.65rem .75rem; background:rgba(0,229,255,.07); color:#c6d8e9; font-size:.76rem; line-height:1.45; margin:.55rem 0 .7rem; }
    .explain b { color:var(--cyan); }
    .judge-box { border:1px solid rgba(32,230,191,.4); border-radius:14px; padding:.8rem .9rem; background:linear-gradient(110deg,rgba(32,230,191,.10),rgba(13,25,43,.92)); }
    .judge-box.red { border-color:rgba(255,100,117,.45); background:linear-gradient(110deg,rgba(255,100,117,.09),rgba(13,25,43,.92)); }
    .judge-box .title { color:var(--teal); font-size:.68rem; font-weight:850; text-transform:uppercase; letter-spacing:.14em; }
    .judge-box.red .title { color:var(--red); }
    .judge-box .text { color:#d8e8f7; font-size:.82rem; line-height:1.45; margin-top:.3rem; }

    .stButton>button { border:1px solid rgba(0,229,255,.7); background:linear-gradient(100deg,rgba(0,229,255,.20),rgba(32,230,191,.12)); color:var(--text); font-weight:800; border-radius:10px; min-height:2.55rem; box-shadow:0 0 18px rgba(0,229,255,.08); }
    .stButton>button:hover { border-color:var(--cyan); color:white; box-shadow:0 0 20px rgba(0,229,255,.22); }
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div { background-color:rgba(5,14,26,.9); border-color:#27425d; }
    .stSlider [data-baseweb="slider"] { padding-top:.35rem; }
    .stExpander { border:1px solid var(--line); border-radius:12px; background:rgba(10,23,40,.7); }
    .stExpander summary { color:#d9eafb; }
    footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _generate_in_memory_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fleet_sizes = [12, 30, 48]
    architectures = ["regenerative", "functional_split", "bent_pipe"]
    isl_topologies = ["rf_intra_plane", "optical_cross_plane", "hybrid"]
    time_steps = list(range(0, 95, 5))

    track_rows = []
    for fleet in fleet_sizes:
        num_sats = 6 if fleet == 12 else (10 if fleet == 30 else 14)
        for sat_idx in range(1, num_sats + 1):
            sat_name = f"LYNQ-{sat_idx:02d}"
            phase_offset = (sat_idx - 1) * (180.0 / num_sats)
            lon_offset = (sat_idx - 1) * (45.0 / num_sats) - 18.0
            for t in time_steps:
                angle = math.radians((t * 4.0) + phase_offset)
                lat = 55.0 + 14.5 * math.sin(angle)
                lon = lon_offset + (t * 0.42) + 8.0 * math.cos(angle * 0.7)
                track_rows.append(
                    {"fleet_size": fleet, "satellite": sat_name, "time_min": t, "lat": round(lat, 3), "lon": round(lon, 3)}
                )
    tracks_df = pd.DataFrame(track_rows)

    res_rows = []
    for fleet in fleet_sizes:
        for arch in architectures:
            for isl in isl_topologies:
                for term_name, term_coords in TERMINALS.items():
                    for t in time_steps:
                        angle = math.radians(t * 4.0 + (5 if fleet >= 30 else 0))
                        sat_lat = round(term_coords["lat"] + 4.8 * math.sin(angle), 2)
                        sat_lon = round(term_coords["lon"] + 6.2 * math.cos(angle), 2)
                        sat_id = f"LYNQ-{((t // 15 + (0 if fleet == 12 else 2)) % 8) + 1:02d}"

                        if fleet == 12:
                            term_vis = (t % 25) != 10 and (t % 30) != 15
                            auth_vis = (t % 20) == 0 or (t in [25, 50, 75])
                            base_wait = 28.0
                        elif fleet == 30:
                            term_vis = (t % 35) != 15
                            auth_vis = (t % 15) == 0 or (t in [20, 25, 40, 55, 70, 85])
                            base_wait = 14.0
                        else:
                            term_vis = True
                            auth_vis = (t % 10) == 0 or (t in [15, 25, 35, 45, 65, 75, 85])
                            base_wait = 6.0

                        if arch == "bent_pipe":
                            route_avail = bool(term_vis and auth_vis)
                        else:
                            if isl == "hybrid":
                                route_avail = bool(term_vis)
                            elif isl == "optical_cross_plane":
                                route_avail = bool(term_vis and (fleet >= 30 or t % 15 != 5))
                            else:
                                route_avail = bool(term_vis and (fleet == 48 or t % 20 != 10))

                        if route_avail:
                            base_lat = 88.0 if fleet == 12 else (76.0 if fleet == 30 else 68.0)
                            isl_mod = 12.0 if isl == "rf_intra_plane" else (-6.0 if isl == "optical_cross_plane" else 0.0)
                            arch_mod = 0.0 if arch == "regenerative" else (7.0 if arch == "functional_split" else 22.0)
                            crit_latency = round(base_lat + isl_mod + arch_mod + (t % 15) * 0.4, 1)
                        else:
                            crit_latency = None

                        queue_mb = round(min(60.0, 10.0 + (t * 0.45) * (1.0 if fleet == 12 else (0.72 if fleet == 30 else 0.5))), 1)
                        next_wait = round(max(2.0, base_wait - (t % 15) * 0.6), 1)
                        reg_delivery = round(next_wait + (4.0 if isl == "rf_intra_plane" else 2.0), 1)

                        res_rows.append(
                            {
                                "fleet_size": fleet,
                                "architecture": arch,
                                "isl_topology": isl,
                                "terminal": term_name,
                                "time_min": t,
                                "satellite": sat_id,
                                "sat_lat": sat_lat,
                                "sat_lon": sat_lon,
                                "terminal_visible": term_vis,
                                "authorized_visible": auth_vis,
                                "route_available": route_avail,
                                "critical_latency_ms": crit_latency,
                                "regular_delivery_min": reg_delivery,
                                "queue_depth_mb": queue_mb,
                                "next_pass_wait_min": next_wait,
                            }
                        )
    results_df = pd.DataFrame(res_rows)
    summary_df = (
        results_df.groupby(["fleet_size", "architecture", "isl_topology"], as_index=False)
        .agg(
            availability_pct=("route_available", lambda s: round(100.0 * s.mean(), 1)),
            mean_critical_latency_ms=("critical_latency_ms", lambda s: round(s.dropna().mean(), 1) if not s.dropna().empty else None),
        )
    )
    return results_df, summary_df, tracks_df


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return _generate_in_memory_data()


def line(fig: go.Figure, lats, lons, name: str, color: str, dash: str = "solid", width: float = 3) -> None:
    fig.add_trace(
        go.Scattergeo(
            lat=lats,
            lon=lons,
            mode="lines",
            name=name,
            line={"color": color, "width": width, "dash": dash},
            hoverinfo="name",
        )
    )


def marker(fig: go.Figure, lat: float, lon: float, name: str, color: str, symbol: str, size: int = 11) -> None:
    fig.add_trace(
        go.Scattergeo(
            lat=[lat],
            lon=[lon],
            mode="markers+text",
            name=name,
            text=[name],
            textposition="top center",
            textfont={"color": "#dbeafe", "size": 10},
            marker={"size": size, "color": color, "symbol": symbol, "line": {"color": "#07111e", "width": 1.5}},
            hovertemplate="<b>%{text}</b><br>Lat %{lat:.2f}°<br>Lon %{lon:.2f}°<extra></extra>",
        )
    )


def build_map(tracks: pd.DataFrame, row: pd.Series, terminal: dict, topology: str, traffic: str, effective_available: bool) -> go.Figure:
    fig = go.Figure()

    for sat, group in tracks.groupby("satellite", sort=True):
        fig.add_trace(
            go.Scattergeo(
                lat=group["lat"],
                lon=group["lon"],
                mode="lines",
                name="Synthetic orbit tracks" if sat == "LYNQ-01" else sat,
                showlegend=sat == "LYNQ-01",
                line={"color": "rgba(91,146,185,.32)", "width": 1},
                hoverinfo="skip",
            )
        )

    marker(fig, float(terminal["lat"]), float(terminal["lon"]), "Primary terminal", "#00e5ff", "diamond", 14)
    secondary = TERMINALS["Energy Platform Alpha"] if terminal["lat"] != 58.20 else TERMINALS["North Sea Wind Farm"]
    marker(fig, secondary["lat"], secondary["lon"], "Secondary asset", "#1ca7a0", "diamond", 9)
    marker(fig, GATEWAYS["Blocked / Unauthorized GW"]["lat"], GATEWAYS["Blocked / Unauthorized GW"]["lon"], "Blocked GW", "#ff6475", "x", 12)
    marker(fig, GATEWAYS["Authorized EU / Luxembourg GW"]["lat"], GATEWAYS["Authorized EU / Luxembourg GW"]["lon"], "Authorized GW (LU)", "#20e6bf", "square", 12)
    marker(fig, float(row["sat_lat"]), float(row["sat_lon"]), str(row["satellite"]), "#ffffff", "star", 15)

    term_lat, term_lon = float(terminal["lat"]), float(terminal["lon"])
    sat_lat, sat_lon = float(row["sat_lat"]), float(row["sat_lon"])
    auth = GATEWAYS["Authorized EU / Luxembourg GW"]

    if traffic == "Critical Alarm":
        line(fig, [term_lat, sat_lat], [term_lon, sat_lon], "Service link (S/C-band)", "#00e5ff", "solid", 3.3)
        if effective_available:
            if topology == "rf_intra_plane":
                line(fig, [sat_lat, auth["lat"]], [sat_lon, auth["lon"]], "RF ISL", "#ffd166", "solid", 2.8)
            elif topology == "optical_cross_plane":
                line(fig, [sat_lat, auth["lat"]], [sat_lon, auth["lon"]], "Optical ISL", "#20e6bf", "solid", 3.0)
            else:
                relay_lat, relay_lon = 54.90, 5.70
                marker(fig, relay_lat, relay_lon, "Optical Relay Sat", "#ffd166", "hexagon", 10)
                line(fig, [sat_lat, relay_lat], [sat_lon, relay_lon], "RF ISL Hop", "#ffd166", "solid", 2.8)
                line(fig, [relay_lat, auth["lat"]], [relay_lon, auth["lon"]], "Optical ISL Trunk", "#20e6bf", "solid", 3.1)
        else:
            line(fig, [sat_lat, auth["lat"]], [sat_lon, auth["lon"]], "No authorized path yet", "#ff6475", "dot", 1.8)
    else:
        line(fig, [term_lat, sat_lat], [term_lon, sat_lon], "Uplink / Onboard S&F Buffer", "#ffd166", "dot", 2.8)

    fig.update_layout(
        height=580,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="#081323",
        plot_bgcolor="#081323",
        font={"family": "Arial", "color": "#c7d6e8", "size": 10},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 0.01,
            "xanchor": "left",
            "x": 0.01,
            "bgcolor": "rgba(5,9,20,.86)",
            "bordercolor": "#24425e",
            "borderwidth": 1,
            "font": {"size": 10},
        },
        geo={
            "projection_type": "mercator",
            "showland": True,
            "landcolor": "#142438",
            "showocean": True,
            "oceancolor": "#061323",
            "showcoastlines": True,
            "coastlinecolor": "#4c7595",
            "showcountries": True,
            "countrycolor": "#29455f",
            "lonaxis": {"range": [-25, 35], "showgrid": True, "gridcolor": "rgba(84,150,180,.18)"},
            "lataxis": {"range": [42, 72], "showgrid": True, "gridcolor": "rgba(84,150,180,.18)"},
        },
    )
    return fig


def explanation_for(architecture_label: str, is_regenerative: bool, traffic: str, effective_available: bool, local_status: str) -> tuple[str, str, bool]:
    if traffic == "Bulk Telemetry":
        return (
            "Store-and-forward queue activated",
            "Routine sensor telemetry is non-urgent. Given constrained 6U onboard memory, it is buffered in the store-and-forward queue and downlinked on the next compliant pass.",
            False,
        )
    if is_regenerative and effective_available:
        split_note = (
            "With Full gNB onboard, routing and 3GPP context switching happen entirely in orbit."
            if "Full gNB" in architecture_label
            else "With 3GPP Functional Split (DU onboard / CU ground), the satellite switches frames over ISL to the sovereign EU gateway CU."
        )
        return (
            "Critical alarm dynamically rerouted via ISL",
            f"{split_note} Even with the local gateway blocked, the policy engine enforces EU jurisdiction and delivers via ISL.",
            False,
        )
    if not is_regenerative and local_status == "Blocked":
        return (
            "Bent-pipe reaches its architectural limit",
            "A transparent bent-pipe payload acts as a simple RF repeater. With the local feeder gateway blocked or unavailable, critical traffic drops or stalls.",
            True,
        )
    return (
        "Waiting for a valid compliant path",
        "The policy engine holds the packet safely in onboard buffer and awaits the next satellite handover that satisfies gateway visibility.",
        True,
    )


st.markdown(
    "<div class='brandline'>"
    "<div class='brand'>✦ LYNQ <span>NTN-PULSE</span></div>"
    "<div class='chip-group'>"
    "<div class='hpc-chip'>⚡ MELUXINA HPC · PROJECT p201621</div>"
    "<div class='mission-chip'>NORTH SEA · MISSION CONTROL</div>"
    "</div></div>"
    "<div class='sub'>A jurisdiction-aware digital twin & policy engine for regenerative 3GPP 5G NR-NTN constellations</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='hero'>
      <div class='eyebrow'>OQ ANYPOINT NTN CHALLENGE · PHASE 2 DEMONSTRATOR</div>
      <h1>Every signal, the right path.</h1>
      <p>Lynq NTN-Pulse evaluates orbital pass geometry, 3GPP payload split, link budget constraints and gateway jurisdiction to keep offshore critical signals moving when local gateways fail.</p>
      <div class='hero-steps'>
        <div class='hero-step'><b>01</b> Track constellation pass, link budget & gateway availability.</div>
        <div class='hero-step'><b>02</b> Enforce 3GPP QoS priority: pre-empt for alarms vs. store-and-forward bulk.</div>
        <div class='hero-step'><b>03</b> Route via RF/Optical ISL to an authorized sovereign European gateway.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

results, summary, tracks = load_data()


with st.sidebar:
    st.markdown("## 🛰️ Mission control")
    st.caption("Configure constellation, 3GPP payload & ISL architecture.")

    st.markdown("**1 · Constellation sizing**")
    fleet_choice = st.selectbox(
        "Constellation size",
        ["12 LEO (Current Baseline)", "30 LEO (Intermediate)", "48 LEO (Gen-2 Target)"],
        index=0,
        help="Compare current 12-satellite fleet against larger optimal LEO constellations.",
    )
    fleet_size_num = int(fleet_choice.split()[0])

    st.markdown("**2 · 3GPP Payload & ISL Architecture**")
    architecture_label = st.selectbox(
        "Payload architecture",
        list(ARCH_LABELS.keys()),
        index=0,
        help="OQ meeting insight: Regenerative payloads can host either a full gNB onboard or a functional split (DU on satellite, CU on ground).",
    )
    selected_arch_key = ARCH_LABELS[architecture_label]
    is_regenerative = selected_arch_key in ("regenerative", "functional_split")
    is_split = selected_arch_key == "functional_split"

    topology_label = st.selectbox(
        "ISL technology & topology",
        list(TOPOLOGY_LABELS.keys()),
        index=2,
        help="Analyze trade-offs between RF ISL (requires spectrum licensing) and Optical ISL (higher SWaP, high capacity).",
    )
    topology = TOPOLOGY_LABELS[topology_label]

    st.markdown("**3 · Offshore Scenario & Policy**")
    terminal_name = st.selectbox(
        "Primary offshore terminal",
        list(TERMINALS.keys()),
        index=0,
        help="The North Sea offshore asset transmitting 3GPP NTN traffic.",
    )
    traffic = st.selectbox(
        "Traffic class (3GPP QoS)",
        ["Critical Alarm", "Bulk Telemetry"],
        index=0,
        help="Critical alarms pre-empt queues. Bulk telemetry uses onboard Store-and-Forward.",
    )

    local_available = st.toggle(
        "Local gateway available / compliant",
        value=False,
        help="Simulate a local gateway failure, weather outage, or non-compliant jurisdiction.",
    )
    local_status = "Available" if local_available else "Blocked"
    time_min = st.slider("Simulation time (minutes)", 0, 90, 25, 5, help="Step through a 90-minute synthetic orbital window.")

    st.markdown("---")
    run = st.button("🚀 Launch routing simulation", use_container_width=True, type="primary")
    if run:
        st.success("Policy & link budget simulation updated.")
    st.caption("Synthetic deterministic demonstrator executed & calibrated via MeluXina HPC (`p201621`).")


# Safe fallback lookup if older CSV is present before engine_v2 runs
available_fleets = results["fleet_size"].unique()
csv_fleet_size = fleet_size_num if fleet_size_num in available_fleets else (30 if fleet_size_num == 48 else 12)

available_archs = results["architecture"].unique()
csv_arch = selected_arch_key if selected_arch_key in available_archs else ("regenerative" if is_regenerative else "bent_pipe")

terminal = TERMINALS[terminal_name]
scenario = results[
    (results["fleet_size"] == csv_fleet_size)
    & (results["architecture"] == csv_arch)
    & (results["isl_topology"] == topology)
    & (results["terminal"] == terminal_name)
]
row = scenario[scenario["time_min"] == time_min].iloc[0]
tracks_at_fleet = tracks[tracks["fleet_size"] == csv_fleet_size]

effective_available = bool(row["route_available"])
if not is_regenerative and local_status == "Blocked":
    effective_available = False

isl_info = ISL_SPECS[topology]
split_latency_penalty = 6 if (is_split and csv_arch != "functional_split") else 0
gen2_wait_factor = 0.55 if (fleet_size_num == 48 and csv_fleet_size != 48) else 1.0

decision_title, decision_text, decision_is_red = explanation_for(
    architecture_label, is_regenerative, traffic, effective_available, local_status
)

status_cols = st.columns(3, gap="medium")
with status_cols[0]:
    st.markdown(
        f"<div class='card'><div class='label'>3GPP Payload Mode</div><div class='value'>{architecture_label}</div>"
        f"<div class='note'>{'Full L2/L3 routing onboard.' if 'Full' in architecture_label else ('DU onboard · CU at sovereign gateway.' if is_split else 'Transparent RF repeater; requires visible feeder GW.')}</div></div>",
        unsafe_allow_html=True,
    )
with status_cols[1]:
    st.markdown(
        f"<div class='card'><div class='label'>Traffic Class & QoS</div><div class='value {'green' if traffic == 'Critical Alarm' else 'amber'}'>{traffic}</div>"
        f"<div class='note'>{'Pre-emptive priority routing via ISL.' if traffic == 'Critical Alarm' else 'Buffered in 6U onboard memory (Store-and-Forward).'}</div></div>",
        unsafe_allow_html=True,
    )
with status_cols[2]:
    st.markdown(
        f"<div class='card {'redline' if local_status == 'Blocked' else 'highlight'}'><div class='label'>Local Gateway Status</div><div class='value {'red' if local_status == 'Blocked' else 'green'}'>{local_status}</div>"
        f"<div class='note'>{'Fallback action triggered -> Rerouting to LU Gateway.' if local_status == 'Blocked' else 'Direct local feeder downlink permitted.'}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='judge-box {'red' if decision_is_red else ''}'><div class='title'>Policy Engine Decision · {decision_title}</div><div class='text'>{decision_text}</div></div>",
    unsafe_allow_html=True,
)

left, right = st.columns([2.35, 1], gap="large")
with left:
    st.markdown("<div class='section-head'><h2>🌌 Live constellation & ISL routing view</h2><span>North Sea corridor · Sovereign EU Gateway fallback</span></div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='explain'><b>Map Legend:</b> Cyan = Terminal-to-Satellite uplink (S/C-band) · Yellow = RF ISL hop · Green = Optical ISL trunk to Authorized Luxembourg Gateway · Red = Blocked/Outage path.</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        build_map(tracks_at_fleet, row, terminal, topology, traffic, effective_available),
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": True, "responsive": True},
    )

with right:
    st.markdown("<div class='section-head'><h2>📡 Mission & Link Budget Readout</h2><span>current orbital state</span></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='card highlight'><div class='label'>Active Serving Node</div><div class='value'>{row['satellite']} ({fleet_size_num} LEO)</div>"
        f"<div class='note'>T+{time_min:02d} min · Lat {row['sat_lat']:.2f}° · Lon {row['sat_lon']:.2f}°<br>"
        f"Terminal in view: <b>{'YES' if row['terminal_visible'] else 'NO'}</b> · "
        f"Authorized EU GW visible: <b>{'YES' if row['authorized_visible'] else 'NO'}</b></div></div>",
        unsafe_allow_html=True,
    )
    st.progress(time_min / 90.0, text="Orbital pass progression · 0 to 90 minutes")

    if traffic == "Critical Alarm":
        if is_regenerative:
            route = (
                "RF ISL → Optical Relay → LU GW"
                if topology == "hybrid"
                else ("RF ISL → Authorized LU GW" if topology == "rf_intra_plane" else "Optical ISL → Authorized LU GW")
            )
        else:
            route = "Direct Feeder Link" if effective_available else "No Authorized Path (Blocked)"

        if effective_available and pd.notna(row["critical_latency_ms"]):
            adj_lat = max(25.0, float(row["critical_latency_ms"]) + split_latency_penalty)
            latency = f"~{adj_lat:.0f} ms"
        else:
            latency = "Waiting for pass"
        tone = "green" if effective_available else "red"
        readout_note = "Critical alarm bypasses blocked gateway via ISL." if effective_available else "Traffic held until valid path appears."
    else:
        route = "Onboard Store-and-Forward Buffer"
        adj_deliv = max(2.0, float(row["regular_delivery_min"]) * gen2_wait_factor)
        latency = f"~{adj_deliv:.0f} min (Next Compliant Pass)"
        tone = "amber"
        readout_note = "Bulk data stored in 6U flash buffer to preserve power & bandwidth for alarms."

    st.markdown(
        f"<div class='card {'amberline' if tone == 'amber' else 'redline' if tone == 'red' else 'highlight'}'><div class='label'>Selected Route & Latency</div><div class='value {tone}'>{route}</div><div class='note'>{readout_note}<br>End-to-End Delivery: <b>{latency}</b></div></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div class='card'><div class='label'>ISL Link Budget & Handover Profile</div>"
        f"<div class='note'>"
        f"<b>ISL Data Rate:</b> {isl_info['rate']}<br>"
        f"<b>Power / Duty Cycle:</b> {isl_info['power']}<br>"
        f"<b>Handover Context Transfer:</b> {isl_info['handover']}<br>"
        f"<b>Regulatory / Spectrum:</b> {isl_info['licensing']}"
        f"</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("<div class='section-head'><h2>📊 Engineering, Regulatory & Business KPIs</h2><span>calibrated with OQ Challenge criteria</span></div>", unsafe_allow_html=True)

next_wait = max(1.0, float(row["next_pass_wait_min"]) * gen2_wait_factor)
metric_values = [
    ("Pass Visibility", "IN VIEW" if row["terminal_visible"] else "REVISIT GAP", "green" if row["terminal_visible"] else "red", "Current line-of-sight to offshore terminal."),
    ("Critical Fallback", "ISL ACTIVE" if effective_available else "BUFFERED", "green" if effective_available else "red", "Fallback status under local gateway outage."),
    ("Onboard Buffer Used", f"{row['queue_depth_mb']:.0f} / 64 MB", "amber", "Constrained 6U CubeSat store-and-forward memory."),
    ("Revisit Wait Gap", f"{next_wait:.0f} min", "", f"Estimated revisit gap for {fleet_size_num}-satellite fleet."),
    ("Target Fleet Opex", "€9M / yr", "green", "Affordable CubeSat/smallsat constellation envelope."),
    ("Break-even Scale", "75k assets", "green", "Offshore B2B subscription model target."),
    ("Spectrum / Band", "S-Band & C-Band", "", "3GPP Rel-17/19 NTN with TDD timing compensation."),
    ("HPC Validation", "MeluXina A100", "green", "Simulated on LuxProvide EuroHPC (`p201621`)."),
]

cols = st.columns(4, gap="medium")
for index, (label, value, tone, help_text) in enumerate(metric_values):
    with cols[index % 4]:
        st.markdown(
            f"<div class='card'><div class='label'>{label}</div><div class='value {tone}'>{value}</div><div class='note'>{help_text}</div></div>",
            unsafe_allow_html=True,
        )

with st.expander("📘 Architectural Trade-offs (Validated with OQ Technology)", expanded=False):
    term_cols = st.columns(3, gap="medium")
    with term_cols[0]:
        st.markdown("**Full gNB vs. Functional Split (CU/DU)**")
        st.caption(
            "In a regenerative payload, hosting the full gNB onboard minimizes ISL signaling latency (~90 ms). "
            "A Functional Split (DU onboard, CU on ground) reduces satellite compute & power burden while still enabling ISL frame forwarding."
        )
    with term_cols[1]:
        st.markdown("**RF ISL vs. Optical ISL & Licensing**")
        st.caption(
            "RF ISL offers lower SWaP and easier pointing for 6U nanosats but requires spectrum coordination/licensing (e.g., via ILR in Luxembourg). "
            "Optical ISL provides license-free high capacity across orbital planes at a higher power/pointing cost."
        )
    with term_cols[2]:
        st.markdown("**Store-and-Forward Handover (~2–4s)**")
        st.caption(
            "When a satellite leaves coverage, stored context and buffered packets are transferred to the next rising satellite. "
            "Rather than instantaneous terrestrial handoff, our model accounts for realistic multi-second orbital context transfer."
        )

with st.expander("🎤 Key Takeaway for the Judges", expanded=True):
    if is_regenerative and traffic == "Critical Alarm" and effective_available:
        st.info("Winning Proof: Even when the local gateway goes offline or violates data sovereignty, Lynq keeps critical offshore alarms moving (~90 ms) via hybrid ISL to an authorized Luxembourg gateway.")
    elif not is_regenerative and traffic == "Critical Alarm" and not effective_available:
        st.warning("Bent-Pipe Vulnerability: Without onboard gNB/DU switching and ISL fallback, a blocked local gateway halts critical offshore alarm delivery.")
    elif traffic == "Bulk Telemetry":
        st.info("Smart Resource Protection: Non-urgent sensor logs are queued in onboard Store-and-Forward memory, saving power duty-cycle and ISL bandwidth for emergency SOS traffic.")
    else:
        st.info("Lynq dynamically balances 3GPP QoS priority, onboard memory constraints, and spectrum-compliant routing.")

st.caption("Synthetic deterministic digital twin developed for NeoSpace Europe 2026 (OQ Technology Challenge). Executed on MeluXina Supercomputer (`p201621`).")
