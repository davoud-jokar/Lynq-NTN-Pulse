"""Lynq NTN-Pulse - North Sea NTN digital-twin demonstration.


Run with:
    streamlit run app.py


The app intentionally uses deterministic mock orbital tracks. It does not
require external ephemeris, GIS, map-tile or physics packages.
"""


from __future__ import annotations


import os
import math
from typing import Dict, List, Tuple


import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st




# -----------------------------------------------------------------------------
# Page and theme
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Lynq NTN-Pulse | Digital Twin",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root {
        --bg: #080d17;
        --panel: #101827;
        --panel-2: #0c1422;
        --line: #213047;
        --cyan: #00e5ff;
        --teal: #19e6c1;
        --muted: #8ea1b8;
        --text: #eef7ff;
        --red: #ff5e6c;
        --amber: #ffca6b;
    }


    html, body, [class*="css"] { font-family: Inter, Arial, sans-serif; }
    .stApp { background: var(--bg); color: var(--text); }
    [data-testid="stHeader"] { background: rgba(8, 13, 23, 0.90); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1625 0%, #09101c 100%);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.25rem; }
    .block-container { padding: 1.55rem 2.25rem 2.5rem; max-width: 1550px; }


    .brand-row {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 1.15rem;
    }
    .brand-lockup { display: flex; gap: 0.8rem; align-items: center; }
    .brand-mark {
        width: 44px; height: 44px; border: 1px solid var(--cyan);
        border-radius: 13px; display: grid; place-items: center;
        color: var(--cyan); font-size: 1.35rem;
        box-shadow: 0 0 22px rgba(0,229,255,0.18);
        background: radial-gradient(circle at 35% 30%, #15354b, #0b1525 65%);
    }
    .brand-name { font-family: 'Space Grotesk', Inter, Arial, sans-serif; font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; }
    .brand-sub { color: var(--muted); font-size: 0.75rem; margin-top: 0.1rem; }
    .status-pill {
        display: inline-flex; align-items: center; gap: 0.42rem;
        border: 1px solid rgba(25,230,193,0.35); border-radius: 999px;
        padding: 0.4rem 0.72rem; color: var(--teal); font-size: 0.75rem;
        background: rgba(25,230,193,0.07); font-weight: 600;
    }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--teal); box-shadow: 0 0 10px var(--teal); }
    .hero {
        border: 1px solid #1e3550; border-radius: 18px; padding: 1.15rem 1.35rem;
        background: linear-gradient(110deg, rgba(0,229,255,0.095), rgba(16,24,39,0.78) 47%, rgba(25,230,193,0.055));
        margin-bottom: 1rem;
    }
    .hero h1 { font-family: 'Space Grotesk', Inter, Arial, sans-serif; font-size: 1.7rem; margin: 0; color: var(--text); }
    .hero p { margin: 0.35rem 0 0; color: #b9c8d9; font-size: 0.88rem; }
    .eyebrow { text-transform: uppercase; letter-spacing: 0.15em; color: var(--cyan); font-size: 0.68rem; font-weight: 700; margin-bottom: 0.3rem; }
    .section-title { font-family: 'Space Grotesk', Inter, Arial, sans-serif; font-size: 1.05rem; color: var(--text); margin: 0 0 0.65rem; }
    .panel {
        border: 1px solid var(--line); border-radius: 15px; padding: 1rem;
        background: linear-gradient(145deg, rgba(16,24,39,0.94), rgba(10,17,29,0.94));
        height: 100%;
    }
    .panel-label { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; }
    .panel-value { color: var(--text); font-family: 'Space Grotesk', Inter, Arial, sans-serif; font-size: 1.2rem; font-weight: 700; margin-top: 0.22rem; }
    .panel-note { color: var(--muted); font-size: 0.77rem; line-height: 1.35; margin-top: 0.22rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.65rem; }
    .kpi-card { border: 1px solid var(--line); border-radius: 12px; padding: 0.78rem 0.85rem; background: var(--panel); min-height: 86px; }
    .kpi-label { color: var(--muted); font-size: 0.69rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-value { color: var(--cyan); font-family: 'Space Grotesk', Inter, Arial, sans-serif; font-size: 1.15rem; font-weight: 700; margin-top: 0.38rem; }
    .kpi-value.green { color: var(--teal); }
    .kpi-value.amber { color: var(--amber); }
    .route-chip { display: inline-block; padding: 0.28rem 0.54rem; border-radius: 6px; color: #04141a; background: var(--cyan); font-size: 0.72rem; font-weight: 800; }
    .route-chip.bulk { background: var(--amber); }
    .small-rule { height: 1px; background: var(--line); margin: 0.82rem 0; }
    .legend-row { display: flex; gap: 0.8rem; flex-wrap: wrap; color: var(--muted); font-size: 0.72rem; margin-top: 0.45rem; }
    .legend-item { display: inline-flex; align-items: center; gap: 0.32rem; }
    .legend-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .footer-note { color: #6f839a; font-size: 0.7rem; margin-top: 0.9rem; text-align: right; }
    div[data-testid="stMetric"] { background: transparent; }
    div[data-testid="stMetricLabel"] { color: var(--muted); }
    div[data-testid="stMetricValue"] { color: var(--cyan); }
    .stButton > button { border-radius: 9px; border: 1px solid rgba(0,229,255,0.55); background: rgba(0,229,255,0.12); color: var(--text); font-weight: 700; }
    .stButton > button:hover { border-color: var(--cyan); color: var(--cyan); }
    .stSelectbox label, .stSlider label, .stRadio label { color: #c7d6e8 !important; font-size: 0.78rem !important; }
    .stProgress > div > div > div > div { background: linear-gradient(90deg, var(--cyan), var(--teal)); }
    @media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } .block-container { padding: 1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)




# -----------------------------------------------------------------------------
# Mock orbital and routing model
# -----------------------------------------------------------------------------
TERMINALS: Dict[str, Dict[str, float | str]] = {
    "North Sea Wind Farm": {"lat": 56.35, "lon": 3.55, "kind": "Offshore wind terminal"},
    "Energy Platform Alpha": {"lat": 58.20, "lon": 1.20, "kind": "Remote energy platform"},
}


GATEWAYS: Dict[str, Dict[str, float | str]] = {
    "Blocked / Unauthorized GW": {"lat": 51.75, "lon": 4.10, "kind": "Restricted local gateway"},
    "Authorized / Cloud GW": {"lat": 55.70, "lon": 8.35, "kind": "EU-authorized cloud gateway"},
}




def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@st.cache_data
def load_simulation_data() -> pd.DataFrame:
    """Load the real processed data from the simulation engine."""
    if os.path.exists("simulation_results.csv"):
        return pd.read_csv("simulation_results.csv")
    return pd.DataFrame(columns=["time_min", "satellite", "lat", "lon"])




def constellation_tracks(
    orbit_minute: int, terminal_lat: float, terminal_lon: float
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float | str]]:
    # 1. Load data from file
    df = load_simulation_data()
    if df.empty:
        st.error("Data file not found! Please run engine.py first.")
        return pd.DataFrame(), pd.DataFrame(), {"lat": terminal_lat, "lon": terminal_lon, "satellite": "No Data"}
    # 2. Extract all tracks for background map lines
    tracks = df[["satellite", "lat", "lon"]].copy()
    # 3. Extract instantaneous positions based on the slider minute
    positions = df[df["time_min"] == orbit_minute].copy()
    # 4. Identify the active satellite (e.g., LYNQ-07)
    target_satellite = "LYNQ-07"
    if target_satellite in positions["satellite"].values:
        active = positions.loc[positions["satellite"] == target_satellite].iloc[0].to_dict()
    elif not positions.empty:
        active = positions.iloc[0].to_dict()
    else:
        active = {"lat": terminal_lat, "lon": terminal_lon, "satellite": "Unknown"}
    return tracks, positions, active




def add_line(
    figure: go.Figure,
    lats: List[float],
    lons: List[float],
    name: str,
    color: str,
    width: float = 2.5,
    dash: str = "solid",
    opacity: float = 0.95,
) -> None:
    figure.add_trace(
        go.Scattergeo(
            lat=lats,
            lon=lons,
            mode="lines",
            name=name,
            line={"color": color, "width": width, "dash": dash},
            opacity=opacity,
            hoverinfo="name",
            showlegend=True,
        )
    )




def add_marker(
    figure: go.Figure,
    lat: float,
    lon: float,
    name: str,
    description: str,
    color: str,
    symbol: str = "circle",
    size: int = 11,
    showlegend: bool = True,
) -> None:
    figure.add_trace(
        go.Scattergeo(
            lat=[lat], lon=[lon], mode="markers+text", name=name,
            text=[name], textposition="top center",
            textfont={"color": "#dbeafe", "size": 10},
            marker={"size": size, "color": color, "symbol": symbol, "line": {"color": "#07111e", "width": 1.5}},
            customdata=[[description]],
            hovertemplate="<b>%{text}</b><br>%{customdata[0]}<br>Lat %{lat:.2f}°<br>Lon %{lon:.2f}°<extra></extra>",
            showlegend=showlegend,
        )
    )




def build_map(
    tracks: pd.DataFrame,
    positions: pd.DataFrame,
    active_satellite: Dict[str, float | str],
    terminal: Dict[str, float | str],
    traffic_type: str,
    local_gateway_status: str,
    has_run: bool,
) -> go.Figure:
    fig = go.Figure()


    # Background orbit tracks.
    for satellite_id, group in tracks.groupby("satellite", sort=True):
        fig.add_trace(
            go.Scattergeo(
                lat=group["lat"], lon=group["lon"], mode="lines",
                name="Orbit tracks" if satellite_id == "LYNQ-01" else satellite_id,
                legendgroup="tracks", showlegend=satellite_id == "LYNQ-01",
                line={"color": "rgba(91, 126, 158, 0.30)", "width": 1},
                hoverinfo="skip",
            )
        )


    # Current constellation positions.
    fig.add_trace(
        go.Scattergeo(
            lat=positions["lat"], lon=positions["lon"], mode="markers",
            name="LEO constellation",
            marker={"size": 6, "color": "#8ba6be", "opacity": 0.82},
            text=positions["satellite"],
            hovertemplate="<b>%{text}</b><br>Current mock position<extra></extra>",
        )
    )


    # Core infrastructure markers.
    add_marker(fig, float(terminal["lat"]), float(terminal["lon"]), "Primary terminal", str(terminal["kind"]), "#00e5ff", "diamond", 14)
    secondary = TERMINALS["Energy Platform Alpha"] if terminal["kind"] != TERMINALS["Energy Platform Alpha"]["kind"] else TERMINALS["North Sea Wind Farm"]
    add_marker(fig, float(secondary["lat"]), float(secondary["lon"]), "Secondary asset", str(secondary["kind"]), "#1ca7a0", "diamond", 9)


    blocked = GATEWAYS["Blocked / Unauthorized GW"]
    authorized = GATEWAYS["Authorized / Cloud GW"]
    add_marker(fig, float(blocked["lat"]), float(blocked["lon"]), "Blocked GW", f"Status: {local_gateway_status}", "#ff5e6c", "x", 12)
    add_marker(fig, float(authorized["lat"]), float(authorized["lon"]), "Authorized GW", str(authorized["kind"]), "#19e6c1", "square", 12)


    # Active pass and policy-selected path.
    sat_lat = float(active_satellite["lat"])
    sat_lon = float(active_satellite["lon"])
    add_marker(fig, sat_lat, sat_lon, "LYNQ-07 active", "Regenerative onboard gNB", "#ffffff", "star", 15)


    if has_run and traffic_type == "Critical Alarm":
        relay_lat, relay_lon = 58.90, 5.70
        add_line(fig, [float(terminal["lat"]), sat_lat], [float(terminal["lon"]), sat_lon], "Service link", "#00e5ff", 3.4)
        add_line(fig, [sat_lat, relay_lat], [sat_lon, relay_lon], "RF ISL", "#ffca6b", 2.8)
        add_line(fig, [relay_lat, float(authorized["lat"])], [relay_lon, float(authorized["lon"])], "Optical relay", "#19e6c1", 3.2)
        add_marker(fig, relay_lat, relay_lon, "Optical relay", "ISL relay node", "#ffca6b", "hexagon", 10)
        # Show the blocked path as a rejected alternative when the local gateway is blocked.
        if local_gateway_status == "Blocked":
            add_line(fig, [sat_lat, float(blocked["lat"])], [sat_lon, float(blocked["lon"])], "Rejected local route", "#ff5e6c", 1.5, "dot", 0.55)
    elif has_run and traffic_type == "Bulk Telemetry":
        add_line(fig, [float(terminal["lat"]), sat_lat], [float(terminal["lon"]), sat_lon], "Uplink / queue", "#ffca6b", 2.8, "dot")


    fig.update_layout(
        height=610,
        margin={"l": 0, "r": 0, "t": 4, "b": 0},
        paper_bgcolor="#0b1220",
        plot_bgcolor="#0b1220",
        font={"family": "Inter, Arial, sans-serif", "color": "#c7d6e8", "size": 10},
        legend={
            "orientation": "h", "yanchor": "bottom", "y": 0.01,
            "xanchor": "left", "x": 0.01, "bgcolor": "rgba(8,13,23,0.80)",
            "bordercolor": "#213047", "borderwidth": 1,
        },
        geo={
            "projection_type": "mercator", "showland": True, "landcolor": "#121d2c",
            "showocean": True, "oceancolor": "#071321", "showlakes": True,
            "lakecolor": "#071321", "showcoastlines": True, "coastlinecolor": "#42617c",
            "countrycolor": "#263c53", "showcountries": True,
            "lonaxis": {"range": [-12, 15], "showgrid": True, "gridcolor": "rgba(84,130,157,0.16)"},
            "lataxis": {"range": [48, 64], "showgrid": True, "gridcolor": "rgba(84,130,157,0.16)"},
        },
        hoverlabel={"bgcolor": "#101827", "bordercolor": "#00e5ff", "font": {"color": "#eef7ff"}},
    )
    return fig




def html_metric(label: str, value: str, tone: str = "") -> str:
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value {tone}">{value}</div></div>'




# -----------------------------------------------------------------------------
# Sidebar: policy engine simulator
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<div class='eyebrow'>Policy engine</div><div class='section-title'>Routing simulator</div>", unsafe_allow_html=True)
    st.caption("Select a traffic class and network condition, then run the policy decision.")
    traffic_type = st.selectbox("Traffic Type", ["Critical Alarm", "Bulk Telemetry"], index=0)
    local_gateway_available = st.toggle("Local Gateway Available", value=False)
    local_gateway_status = "Available" if local_gateway_available else "Blocked"
    orbit_minute = st.slider("Simulation time / orbital pass", min_value=0, max_value=90, value=45, step=5)
    run_simulation = st.button("Run Routing Simulation", use_container_width=True, type="primary")


    if "has_run" not in st.session_state:
        st.session_state.has_run = True
    if run_simulation:
        st.session_state.has_run = True
        st.session_state.last_run = f"t+{orbit_minute:02d} min"


    st.markdown("<div class='small-rule'></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-label'>Demo scope</div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-note'>12 mock LEO satellites<br>North Sea basin: 51–61°N, -5–10°E<br>Regenerative gNB + ISL policy routing</div>", unsafe_allow_html=True)
    st.markdown("<div class='small-rule'></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-label'>Brand line</div><div class='panel-value' style='font-size:0.98rem;'>Every signal, the right path.</div>", unsafe_allow_html=True)




# -----------------------------------------------------------------------------
# Main dashboard
# -----------------------------------------------------------------------------
selected_terminal_name = st.session_state.get("selected_terminal", "North Sea Wind Farm")
terminal_name = st.selectbox("Primary offshore asset", list(TERMINALS.keys()), index=list(TERMINALS.keys()).index(selected_terminal_name))
st.session_state.selected_terminal = terminal_name
terminal = TERMINALS[terminal_name]


tracks, positions, active_satellite = constellation_tracks(
    orbit_minute, float(terminal["lat"]), float(terminal["lon"])
)


st.markdown(
    """
    <div class="brand-row">
      <div class="brand-lockup">
        <div class="brand-mark">✦</div>
        <div><div class="brand-name">Lynq NTN-Pulse</div><div class="brand-sub">Regenerative 5G NR-NTN digital twin</div></div>
      </div>
      <div class="status-pill"><span class="status-dot"></span> DIGITAL TWIN ONLINE</div>
    </div>
    <div class="hero">
      <div class="eyebrow">North Sea offshore energy basin · 12 LEO satellites</div>
      <h1>Every signal, the right path.</h1>
      <p>Policy-controlled routing for the regenerative onboard gNB: prioritise critical alarms, bypass blocked gateways and queue routine telemetry.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


left, right = st.columns([2.25, 1], gap="large")
with left:
    st.markdown("<div class='section-title'>Constellation and route state</div>", unsafe_allow_html=True)
    st.plotly_chart(
        build_map(
            tracks,
            positions,
            active_satellite,
            terminal,
            traffic_type,
            local_gateway_status,
            st.session_state.has_run,
        ),
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": True, "responsive": True},
    )
    st.markdown(
        "<div class='legend-row'><span class='legend-item'><span class='legend-dot' style='background:#00e5ff'></span>Service link</span><span class='legend-item'><span class='legend-dot' style='background:#ffca6b'></span>RF ISL / queue</span><span class='legend-item'><span class='legend-dot' style='background:#19e6c1'></span>Authorized cloud path</span><span class='legend-item'><span class='legend-dot' style='background:#ff5e6c'></span>Blocked or rejected</span></div>",
        unsafe_allow_html=True,
    )


with right:
    st.markdown("<div class='section-title'>Pass telemetry</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='panel'>
          <div class='panel-label'>Active satellite</div><div class='panel-value'>{active_satellite['satellite']}</div>
          <div class='panel-note'>Regenerative gNB payload · mock position<br>Lat {float(active_satellite['lat']):.2f}° · Lon {float(active_satellite['lon']):.2f}°</div>
          <div class='small-rule'></div>
          <div class='panel-label'>Orbital pass</div><div class='panel-value'>T+{orbit_minute:02d} min</div>
          <div class='panel-note'>Satellite crosses the selected terminal at approximately T+45 min.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(orbit_minute / 90.0, text="Pass progress")
    st.markdown("<div style='height:0.55rem'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Policy decision</div>", unsafe_allow_html=True)


    if traffic_type == "Critical Alarm":
        route = "RF ISL → Optical Relay → Authorized GW"
        route_class = "route-chip"
        latency = "~90 ms"
        qos = "High Priority"
        delivery = "Immediate"
        decision_note = "Critical traffic bypasses the local gateway when blocked and is forwarded through the authorised cloud path."
    else:
        route = "Store & Forward"
        route_class = "route-chip bulk"
        latency = "Up to 90 min"
        qos = "Buffered Telemetry"
        delivery = "~45 min"
        decision_note = "Routine telemetry is queued onboard and released during the next suitable feeder or gateway pass."


    st.markdown(
        f"""
        <div class='panel'>
          <span class='{route_class}'>{traffic_type.upper()}</span>
          <div class='panel-value' style='font-size:1rem; margin-top:0.65rem;'>{route}</div>
          <div class='small-rule'></div>
          <div class='panel-note'>{decision_note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# KPI row
st.markdown("<div style='height:0.7rem'></div><div class='section-title'>Operational and business KPIs</div>", unsafe_allow_html=True)
queue_depth = "0 MB" if traffic_type == "Critical Alarm" else "45 MB"
st.markdown(
    "<div class='metric-grid'>"
    + html_metric("Selected route", route)
    + html_metric("Latency / delivery", latency, "green" if traffic_type == "Critical Alarm" else "amber")
    + html_metric("QoS policy", qos)
    + html_metric("Queue depth", queue_depth, "amber" if traffic_type == "Bulk Telemetry" else "green")
    + html_metric("Target Opex", "€9M / yr", "green")
    + html_metric("Break-even", "75k assets", "green")
    + html_metric("Local gateway", local_gateway_status, "green" if local_gateway_status == "Available" else "")
    + html_metric("Coverage basin", "51–61°N", "")
    + "</div>",
    unsafe_allow_html=True,
)


st.markdown(
    "<div class='footer-note'>Simulation uses deterministic mock ephemeris for demonstration only. It is not an operational flight-dynamics or spectrum-compliance tool.</div>",
    unsafe_allow_html=True,
)