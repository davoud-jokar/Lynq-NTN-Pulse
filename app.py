"""Lynq NTN-Pulse v3 — space-tech digital-twin dashboard.

Keep app_v2.py as the stable backup. Run this version after engine_v2.py:

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
    "Authorized / Cloud GW": {"lat": 55.70, "lon": 8.35},
}

TOPOLOGY_LABELS = {
    "RF intra-plane": "rf_intra_plane",
    "Optical cross-plane": "optical_cross_plane",
    "Hybrid RF + optical": "hybrid",
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
    .mission-chip { border:1px solid rgba(0,229,255,.42); color:var(--cyan); border-radius:999px; padding:.38rem .72rem; font-size:.65rem; letter-spacing:.12em; font-weight:800; white-space:nowrap; }
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
    .mini-title { color:#dcecff; font-weight:800; font-size:.78rem; margin-bottom:.2rem; }
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


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    results = pd.read_csv(ROOT / "simulation_results_v2.csv")
    summary = pd.read_csv(ROOT / "scenario_summary_v2.csv")
    tracks = pd.read_csv(ROOT / "orbit_tracks_v2.csv")
    return results, summary, tracks


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
                name="Mock orbit tracks" if sat == "LYNQ-01" else sat,
                showlegend=sat == "LYNQ-01",
                line={"color": "rgba(91,146,185,.32)", "width": 1},
                hoverinfo="skip",
            )
        )

    marker(fig, float(terminal["lat"]), float(terminal["lon"]), "Primary terminal", "#00e5ff", "diamond", 14)
    secondary = TERMINALS["Energy Platform Alpha"] if terminal["lat"] != 58.20 else TERMINALS["North Sea Wind Farm"]
    marker(fig, secondary["lat"], secondary["lon"], "Secondary asset", "#1ca7a0", "diamond", 9)
    marker(fig, GATEWAYS["Blocked / Unauthorized GW"]["lat"], GATEWAYS["Blocked / Unauthorized GW"]["lon"], "Blocked GW", "#ff6475", "x", 12)
    marker(fig, GATEWAYS["Authorized / Cloud GW"]["lat"], GATEWAYS["Authorized / Cloud GW"]["lon"], "Authorized GW", "#20e6bf", "square", 12)
    marker(fig, float(row["sat_lat"]), float(row["sat_lon"]), str(row["satellite"]), "#ffffff", "star", 15)

    term_lat, term_lon = float(terminal["lat"]), float(terminal["lon"])
    sat_lat, sat_lon = float(row["sat_lat"]), float(row["sat_lon"])
    auth = GATEWAYS["Authorized / Cloud GW"]

    if traffic == "Critical Alarm":
        line(fig, [term_lat, sat_lat], [term_lon, sat_lon], "Service link", "#00e5ff", "solid", 3.3)
        if effective_available:
            if topology == "rf_intra_plane":
                line(fig, [sat_lat, auth["lat"]], [sat_lon, auth["lon"]], "RF ISL", "#ffd166", "solid", 2.8)
            elif topology == "optical_cross_plane":
                line(fig, [sat_lat, auth["lat"]], [sat_lon, auth["lon"]], "Optical ISL", "#20e6bf", "solid", 3.0)
            else:
                relay_lat, relay_lon = 58.90, 5.70
                marker(fig, relay_lat, relay_lon, "Optical relay", "#ffd166", "hexagon", 10)
                line(fig, [sat_lat, relay_lat], [sat_lon, relay_lon], "RF ISL", "#ffd166", "solid", 2.8)
                line(fig, [relay_lat, auth["lat"]], [relay_lon, auth["lon"]], "Optical relay", "#20e6bf", "solid", 3.1)
        else:
            line(fig, [sat_lat, auth["lat"]], [sat_lon, auth["lon"]], "No authorised path yet", "#ff6475", "dot", 1.8)
    else:
        line(fig, [term_lat, sat_lat], [term_lon, sat_lon], "Uplink / onboard queue", "#ffd166", "dot", 2.8)

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
            "lonaxis": {"range": [-30, 40], "showgrid": True, "gridcolor": "rgba(84,150,180,.18)"},
            "lataxis": {"range": [38, 74], "showgrid": True, "gridcolor": "rgba(84,150,180,.18)"},
        },
    )
    return fig


def explanation_for(architecture: str, traffic: str, effective_available: bool, local_status: str) -> tuple[str, str, bool]:
    if traffic == "Bulk Telemetry":
        return (
            "Store-and-forward is selected",
            "Routine telemetry is not urgent. The satellite stores it onboard and sends it later when a suitable gateway or path is available.",
            False,
        )
    if architecture == "regenerative" and effective_available:
        return (
            "The alarm keeps moving",
            "The onboard gNB processes the critical packet in orbit. Because the local gateway is blocked, the policy engine uses the authorized gateway through an ISL route.",
            False,
        )
    if architecture == "bent_pipe" and local_status == "Blocked":
        return (
            "Bent-pipe reaches its limit",
            "A bent-pipe satellite mainly relays the signal. With the local gateway blocked, it cannot complete the critical delivery through the required feeder path.",
            True,
        )
    return (
        "Waiting for a valid path",
        "The policy engine keeps the packet safe and waits for the next route that satisfies the gateway and visibility constraints.",
        True,
    )


st.markdown(
    "<div class='brandline'><div class='brand'>✦ LYNQ <span>NTN-PULSE</span></div><div class='mission-chip'>NORTH SEA · MISSION CONTROL</div></div>"
    "<div class='sub'>A readable digital twin for regenerative 5G NR-NTN routing decisions</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='hero'>
      <div class='eyebrow'>SATELLITE NETWORK OPERATIONS · PHASE 2 DEMONSTRATOR</div>
      <h1>Every signal, the right path.</h1>
      <p>Lynq NTN-Pulse watches the satellite pass, traffic priority and gateway status, then chooses the safest available route for each industrial message.</p>
      <div class='hero-steps'>
        <div class='hero-step'><b>01</b> Observe satellite visibility, gateway status and link availability.</div>
        <div class='hero-step'><b>02</b> Classify the message: critical alarm or routine telemetry.</div>
        <div class='hero-step'><b>03</b> Route immediately, relay through ISL, or store for the next pass.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    results, summary, tracks = load_data()
except FileNotFoundError:
    st.error("Run engine_v2.py first. It must create the three v2 CSV files in this folder.")
    st.stop()


with st.sidebar:
    st.markdown("## 🛰️ Mission control")
    st.caption("Choose a scenario, then launch the routing decision.")

    st.markdown("**1 · Constellation**")
    fleet_size = st.selectbox(
        "Fleet size",
        [12, 30],
        index=0,
        help="Compare the current 12-satellite scenario with the planned 30-satellite scenario.",
    )

    st.markdown("**2 · Network architecture**")
    architecture_label = st.selectbox(
        "Payload architecture",
        ["Regenerative gNB", "Bent-pipe"],
        index=0,
        help="Regenerative gNB processes selected network functions onboard. Bent-pipe mainly relays the signal to a ground gateway.",
    )
    architecture = "regenerative" if architecture_label.startswith("Regenerative") else "bent_pipe"
    st.caption(
        "Regenerative = decisions can be made in orbit.\n\nBent-pipe = delivery depends more directly on a visible feeder gateway."
    )

    topology_label = st.selectbox(
        "ISL topology",
        list(TOPOLOGY_LABELS.keys()),
        index=2,
        help="ISL means inter-satellite link. Hybrid combines an RF hop with an optical relay.",
    )
    topology = TOPOLOGY_LABELS[topology_label]

    st.markdown("**3 · Industrial scenario**")
    terminal_name = st.selectbox(
        "Primary terminal",
        list(TERMINALS.keys()),
        index=0,
        help="The offshore asset sending data to the constellation.",
    )
    traffic = st.selectbox(
        "Traffic type",
        ["Critical Alarm", "Bulk Telemetry"],
        index=0,
        help="Critical alarms need a fast route. Bulk telemetry can wait and be stored onboard.",
    )

    local_available = st.toggle(
        "Local gateway available",
        value=False,
        help="Turn on only when a nearby gateway is permitted and reachable. The demo starts with it blocked to show the policy decision.",
    )
    local_status = "Available" if local_available else "Blocked"
    time_min = st.slider("Simulation time (minutes)", 0, 90, 25, 5, help="Move through a synthetic 90-minute orbital pass.")

    st.markdown("---")
    run = st.button("🚀 Launch routing simulation", use_container_width=True, type="primary")
    if run:
        st.success("Routing decision refreshed.")
    st.caption("This is a synthetic, deterministic engineering demonstrator. It is not flight-certified orbital software.")


terminal = TERMINALS[terminal_name]
scenario = results[
    (results["fleet_size"] == fleet_size)
    & (results["architecture"] == architecture)
    & (results["isl_topology"] == topology)
    & (results["terminal"] == terminal_name)
]
row = scenario[scenario["time_min"] == time_min].iloc[0]
tracks_at_fleet = tracks[tracks["fleet_size"] == fleet_size]

# The local gateway is a policy input. A blocked local gateway prevents bent-pipe delivery.
effective_available = bool(row["route_available"])
if architecture == "bent_pipe" and local_status == "Blocked":
    effective_available = False

decision_title, decision_text, decision_is_red = explanation_for(architecture, traffic, effective_available, local_status)

status_cols = st.columns(3, gap="medium")
with status_cols[0]:
    st.markdown(
        f"<div class='card'><div class='label'>Active architecture</div><div class='value'>{architecture_label}</div><div class='note'>{'Network functions can be processed onboard.' if architecture == 'regenerative' else 'Signal processing depends more directly on the feeder gateway.'}</div></div>",
        unsafe_allow_html=True,
    )
with status_cols[1]:
    st.markdown(
        f"<div class='card'><div class='label'>Message priority</div><div class='value {'green' if traffic == 'Critical Alarm' else 'amber'}'>{traffic}</div><div class='note'>{'Fast delivery is preferred.' if traffic == 'Critical Alarm' else 'Delay is acceptable; protect the link for urgent traffic.'}</div></div>",
        unsafe_allow_html=True,
    )
with status_cols[2]:
    st.markdown(
        f"<div class='card {'redline' if local_status == 'Blocked' else 'highlight'}'><div class='label'>Local gateway</div><div class='value {'red' if local_status == 'Blocked' else 'green'}'>{local_status}</div><div class='note'>{'Policy must find an authorized alternative.' if local_status == 'Blocked' else 'Direct local delivery is permitted in this scenario.'}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='judge-box {'red' if decision_is_red else ''}'><div class='title'>Policy engine decision · {decision_title}</div><div class='text'>{decision_text}</div></div>",
    unsafe_allow_html=True,
)

left, right = st.columns([2.35, 1], gap="large")
with left:
    st.markdown("<div class='section-head'><h2>🌌 Live constellation view</h2><span>North Sea · synthetic orbital pass</span></div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='explain'><b>How to read the map:</b> cyan = terminal-to-satellite service link; yellow = RF inter-satellite hop; green = optical relay; red = blocked or unavailable path.</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        build_map(tracks_at_fleet, row, terminal, topology, traffic, effective_available),
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": True, "responsive": True},
    )

with right:
    st.markdown("<div class='section-head'><h2>📡 Mission readout</h2><span>current pass</span></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='card highlight'><div class='label'>Active satellite</div><div class='value'>{row['satellite']}</div><div class='note'>T+{time_min:02d} min · Lat {row['sat_lat']:.2f}° · Lon {row['sat_lon']:.2f}°<br>Terminal in view: <b>{'YES' if row['terminal_visible'] else 'NO'}</b><br>Authorized gateway visible: <b>{'YES' if row['authorized_visible'] else 'NO'}</b></div></div>",
        unsafe_allow_html=True,
    )
    st.progress(time_min / 90.0, text="Orbital pass progress · 0 to 90 minutes")

    if traffic == "Critical Alarm":
        if architecture == "regenerative":
            route = "RF ISL → Optical Relay → Authorized GW" if topology == "hybrid" else ("RF ISL → Authorized GW" if topology == "rf_intra_plane" else "Optical ISL → Authorized GW")
        else:
            route = "Direct feeder link" if effective_available else "No authorized path yet"
        latency = f"{row['critical_latency_ms']:.0f} ms" if effective_available and pd.notna(row["critical_latency_ms"]) else "Waiting"
        tone = "green" if effective_available else "red"
        readout_note = "Critical alarm is routed immediately when a valid path exists." if effective_available else "Critical traffic waits for the next valid pass or gateway path."
    else:
        route = "Store & Forward"
        latency = f"{row['regular_delivery_min']:.0f} min"
        tone = "amber"
        readout_note = "Routine telemetry is buffered onboard and delivered on the next suitable path."

    st.markdown(
        f"<div class='card {'amberline' if tone == 'amber' else 'redline' if tone == 'red' else 'highlight'}'><div class='label'>{traffic} · selected route</div><div class='value {tone}'>{route}</div><div class='note'>{readout_note}<br>Estimated latency / delivery: <b>{latency}</b></div></div>",
        unsafe_allow_html=True,
    )

st.markdown("<div class='section-head'><h2>📊 Operational and business KPIs</h2><span>live scenario indicators</span></div>", unsafe_allow_html=True)
st.markdown(
    "<div class='explain'><b>Important:</b> visibility, queue and delivery are simulation outputs. Target Opex and break-even are business-case assumptions that must be validated with OQ and the first industrial customer.</div>",
    unsafe_allow_html=True,
)

metric_values = [
    ("Visibility", "IN VIEW" if row["terminal_visible"] else "NEXT PASS", "green" if row["terminal_visible"] else "red", "Can the satellite see the terminal now?"),
    ("Critical delivery", "PATH READY" if effective_available else "WAIT", "green" if effective_available else "red", "Is an authorized route available?"),
    ("Queue depth", f"{row['queue_depth_mb']:.0f} MB", "amber", "How much routine data is waiting onboard?"),
    ("Next pass", f"{row['next_pass_wait_min']:.0f} min", "", "Estimated wait for another suitable path."),
    ("Target Opex", "€9M / yr", "green", "Current business-case target."),
    ("Break-even", "75k assets", "green", "Current business-case assumption."),
    ("Fleet", f"{fleet_size} LEO", "", "Scenario fleet size."),
    ("Gateway", local_status, "green" if local_available else "red", "Local gateway policy status."),
]

cols = st.columns(4, gap="medium")
for index, (label, value, tone, help_text) in enumerate(metric_values):
    with cols[index % 4]:
        st.markdown(
            f"<div class='card'><div class='label'>{label}</div><div class='value {tone}'>{value}</div><div class='note'>{help_text}</div></div>",
            unsafe_allow_html=True,
        )

with st.expander("📘 What do the main technical terms mean?", expanded=False):
    term_cols = st.columns(3, gap="medium")
    with term_cols[0]:
        st.markdown("**Regenerative gNB**")
        st.caption("The satellite performs selected 5G network processing onboard. It can make routing decisions before the data reaches the ground.")
    with term_cols[1]:
        st.markdown("**Bent-pipe**")
        st.caption("The satellite mainly relays the radio signal. Network processing depends more strongly on a visible and authorized ground gateway.")
    with term_cols[2]:
        st.markdown("**Store-and-forward**")
        st.caption("Non-urgent data is stored onboard and delivered later. This protects critical traffic when a direct path is not available.")

with st.expander("🎤 One-sentence explanation for the judges", expanded=False):
    if architecture == "regenerative" and traffic == "Critical Alarm" and effective_available:
        st.info("Even when the local gateway is blocked, Lynq keeps a critical offshore alarm moving by processing it onboard and selecting an authorized ISL route.")
    elif architecture == "bent_pipe" and traffic == "Critical Alarm" and not effective_available:
        st.warning("This is the bent-pipe limit: when the required gateway path is blocked, critical delivery must wait.")
    elif traffic == "Bulk Telemetry":
        st.info("Lynq protects urgent traffic by buffering routine telemetry onboard and sending it when the next suitable path appears.")
    else:
        st.info("Lynq compares visibility, traffic priority and gateway policy before selecting a route.")

st.caption("Synthetic deterministic scenario model for the NeoSpace demonstration. Validate orbital, RF, spectrum and regulatory assumptions with OQ Technology and LuxProvide before operational use.")
