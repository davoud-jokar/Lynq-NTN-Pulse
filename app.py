"""Lynq NTN-Pulse mission dashboard. Run: python -m streamlit run app.py"""
from __future__ import annotations

from dataclasses import asdict, replace
import io
import json
import math
import zipfile
from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import engine

st.set_page_config(page_title="Lynq NTN-Pulse | Mission Control", page_icon="🛰️", layout="wide")

# The existing team's dark/cyan visual identity is retained.
st.markdown("""
<style>
:root {--cyan:#00e5ff;--teal:#20e6bf;--muted:#9db0c6;--text:#eef8ff;--red:#ff6475;--amber:#ffd166;}
.stApp {color:var(--text);background:radial-gradient(circle at 80% 4%,rgba(0,229,255,.13) 0 1px,transparent 2px),radial-gradient(circle at 22% 18%,rgba(255,255,255,.20) 0 1px,transparent 2px),linear-gradient(135deg,#050914 0%,#081426 52%,#050914 100%);}
.block-container {max-width:1580px;padding:1.2rem 1.8rem 2.2rem;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#081323,#0a1728);border-right:1px solid #1f3a57;}
.brandline {display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;}
.brand {font-size:1.5rem;font-weight:850;letter-spacing:.08em;color:var(--text);}.brand span{color:var(--cyan);}
.mission-chip {border:1px solid rgba(0,229,255,.45);color:var(--cyan);border-radius:999px;padding:.35rem .75rem;font-size:.7rem;letter-spacing:.09em;}
.hero {font-size:2.45rem;font-weight:750;line-height:1.2;margin:1rem 0 .45rem;color:white;}
.sub {color:var(--muted);font-size:.95rem;margin-bottom:.8rem;}
.explain {border-left:3px solid var(--cyan);padding:.6rem .8rem;background:rgba(0,229,255,.07);color:#c6d8e9;font-size:.85rem;margin:.5rem 0 1rem;}
.pipeline-wrap {border:1px solid #264868;border-radius:16px;padding:1rem;background:linear-gradient(110deg,rgba(8,20,38,.95),rgba(14,30,52,.92));margin:.7rem 0;}
.pipe-header {display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.7rem;margin-bottom:.75rem;}
.pipe-title {font-size:.75rem;letter-spacing:.12em;color:var(--cyan);font-weight:800;}
.pipe-badge {font-size:.8rem;padding:.3rem .7rem;border-radius:8px;border:1px solid currentColor;}
.green{color:var(--teal);}.amber{color:var(--amber);}.red{color:var(--red);}
.pipe-grid {display:flex;align-items:center;flex-wrap:wrap;gap:.45rem;}
.pipe-node {border:1px solid #294969;border-radius:10px;padding:.5rem .75rem;background:rgba(6,14,26,.75);font-size:.85rem;}
.pipe-arrow {color:var(--cyan);}.pipe-step {color:#88a4c0;font-size:.65rem;text-transform:uppercase;}
.card {border:1px solid #1f3a57;border-radius:14px;padding:.85rem;background:rgba(13,25,43,.9);margin-bottom:.6rem;}
.label {color:#88a1bb;font-size:.7rem;text-transform:uppercase;letter-spacing:.09em;}
.value {font-size:1.3rem;font-weight:800;margin:.25rem 0;color:var(--cyan);}
.note {color:var(--muted);font-size:.82rem;line-height:1.5;}.note b {color:#dcecff;}
[data-testid="stMetric"] {background:rgba(13,25,43,.9);border:1px solid #1f3a57;border-radius:12px;padding:.8rem;}
@media(max-width:700px){.hero{font-size:1.8rem;}.block-container{padding:.8rem;}}
</style>
""", unsafe_allow_html=True)

ARCH_LABELS = {"regenerative": "Full gNB onboard", "functional_split": "Split RAN: DU orbit / CU ground", "bent_pipe": "Transparent bent-pipe"}
TOPOLOGY_LABELS = {"hybrid": "Hybrid RF + optical", "rf_intra_plane": "RF neighbours in one plane", "optical_cross_plane": "Optical across planes"}
COLORS = {"Service": "#00e5ff", "RF ISL": "#ffd166", "Optical ISL": "#20e6bf", "Feeder": "#85f4a8"}


@st.cache_data(show_spinner=False, max_entries=16)
def run_model(parameters: dict, source_hash: str):
    # source_hash invalidates the cache when engine.py changes.
    return engine.simulate(engine.Config(**parameters))


def fmt(value, digits=1, suffix=""):
    return "—" if value is None or pd.isna(value) else f"{float(value):,.{digits}f}{suffix}"


def jump(time_value, traffic=None):
    st.session_state["clock"] = float(time_value)
    if traffic is not None:
        st.session_state["traffic"] = traffic


def advance(step, maximum):
    st.session_state["clock"] = float(np.clip(st.session_state["clock"] + step, 0, maximum))


def footprint(lat, lon, angular_radius):
    bearings = np.linspace(0, 2 * np.pi, 100)
    la, lo = np.radians([lat, lon])
    latitudes = np.arcsin(np.sin(la) * np.cos(angular_radius) + np.cos(la) * np.sin(angular_radius) * np.cos(bearings))
    longitudes = lo + np.arctan2(np.sin(bearings) * np.sin(angular_radius) * np.cos(la), np.cos(angular_radius) - np.sin(la) * np.sin(latitudes))
    return np.degrees(latitudes), (np.degrees(longitudes) + 180) % 360 - 180


def map_figure(tracks, row, c, view, edges, meta):
    time = row.time_min
    now = tracks[tracks.time_min == time].set_index("satellite")
    nodes = {n: (float(v.lat), float(v.lon)) for n, v in now.iterrows()}
    nodes.update({k: (v["lat"], v["lon"]) for k, v in engine.GATEWAYS.items()})
    nodes[c.terminal] = tuple(engine.TERMINALS[c.terminal].values())
    fig = go.Figure()
    for _, g in tracks[(tracks.time_min <= time) & (tracks.time_min >= time - 12)].groupby("satellite"):
        la, lo = [], []
        previous = None
        for point in g.itertuples():
            if previous is not None and abs(point.lon - previous) > 180:
                la.append(None); lo.append(None)
            la.append(point.lat); lo.append(point.lon); previous = point.lon
        fig.add_trace(go.Scattergeo(lat=la, lon=lo, mode="lines", line=dict(color="rgba(95,155,205,.35)", width=1), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scattergeo(lat=now.lat, lon=now.lon, text=now.index, name="Satellite subpoints", mode="markers", marker=dict(size=7,color="#72a9ff"), hovertemplate="%{text}<br>%{lat:.2f}°, %{lon:.2f}°<extra></extra>"))
    ground_names = [c.terminal, *engine.GATEWAYS]
    ground_colors = ["#00e5ff", "#20e6bf" if c.local_enabled else "#ff6475", "#20e6bf" if c.alternative_enabled else "#ff6475"]
    fig.add_trace(go.Scattergeo(lat=[nodes[n][0] for n in ground_names],lon=[nodes[n][1] for n in ground_names],text=ground_names,mode="markers+text",textposition="top center",textfont=dict(color="white",size=10),marker=dict(size=12,color=ground_colors,symbol=["diamond","square","square"]),name="Terminal / gateway"))
    seen = set()
    for edge in edges:
        a, b = nodes[edge["a"]], nodes[edge["b"]]
        kind = edge["kind"]
        fig.add_trace(go.Scattergeo(lat=[a[0],b[0]],lon=[a[1],b[1]],mode="lines+markers",line=dict(color=COLORS[kind],width=3),marker=dict(size=5),name=kind,legendgroup=kind,showlegend=kind not in seen,hovertext=f"{edge['a']} → {edge['b']}<br>{edge['distance_km']:.1f} km · {edge['rate_mbps']:g} Mbps assumption",hoverinfo="text"))
        seen.add(kind)
    active = [e["b"] for e in edges if e["b"] in now.index]
    if active:
        fig.add_trace(go.Scattergeo(lat=[nodes[n][0] for n in active],lon=[nodes[n][1] for n in active],text=active,mode="markers+text",textposition="bottom center",textfont=dict(color="white",size=10),marker=dict(size=13,color="white",symbol="star"),name="Route satellites"))
        la, lo = footprint(*nodes[active[0]], meta["footprint_ground_radius_km"] / engine.R_EARTH)
        fig.add_trace(go.Scattergeo(lat=la,lon=lo,mode="lines",line=dict(color="rgba(0,229,255,.45)",width=1,dash="dash"),name="Geometric footprint",hoverinfo="name"))
    queued = json.loads(row.onboard_queue_by_sat)
    if queued:
        fig.add_trace(go.Scattergeo(lat=[nodes[n][0] for n in queued],lon=[nodes[n][1] for n in queued],text=[f"{n}: {mb:.2f} MB retained" for n,mb in queued.items()],hoverinfo="text",mode="markers",marker=dict(size=11,color="#ffd166",symbol="circle-open",line=dict(width=2)),name="Stored telemetry"))
    geo = dict(showland=True,landcolor="#132438",showocean=True,oceancolor="#061222",showcoastlines=True,coastlinecolor="#4c7595",showcountries=True,countrycolor="#29455f",bgcolor="#081323")
    if view == "3D globe":
        geo.update(projection_type="orthographic",projection_rotation=dict(lon=5,lat=54,roll=0))
    elif view == "Global map":
        geo.update(projection_type="natural earth")
    else:
        geo.update(projection_type="mercator",lonaxis=dict(range=[-24,30],showgrid=True,gridcolor="#203449"),lataxis=dict(range=[43,72],showgrid=True,gridcolor="#203449"))
    fig.update_layout(height=540,geo=geo,margin=dict(l=0,r=0,t=5,b=5),paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#c7d6e8"),legend=dict(orientation="h",y=-.06,font=dict(size=10)),uirevision=f"{view}-{c.fleet_size}")
    return fig


def timeline_figure(df, time, deadline):
    f=go.Figure()
    f.add_trace(go.Scatter(x=df.time_min,y=df.latency_ms,name="Active-path delay",mode="lines",connectgaps=False,line=dict(color="#00e5ff",width=2)))
    f.add_trace(go.Scatter(x=df.time_min,y=df.ground_queue_mb,name="Terminal queue",yaxis="y2",mode="lines",line=dict(color="#72a9ff",width=2)))
    f.add_trace(go.Scatter(x=df.time_min,y=df.onboard_queue_mb,name="Onboard queue",yaxis="y2",mode="lines",line=dict(color="#ffd166",width=2)))
    f.add_hline(y=deadline,line_dash="dot",line_color="#ff6475",annotation_text="Alarm target")
    f.add_vline(x=time,line_dash="dash",line_color="#20e6bf")
    ymax=max(deadline*1.15,float(df.latency_ms.max())*1.15 if df.latency_ms.notna().any() else 0)
    f.update_layout(height=270,margin=dict(l=5,r=5,t=40,b=0),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#081323",font=dict(color="#c7d6e8",size=11),legend=dict(orientation="h",y=1.15),xaxis=dict(title="Simulation minute",gridcolor="#203449"),yaxis=dict(title="One-way delay (ms)",range=[0,ymax],gridcolor="#203449"),yaxis2=dict(title="Queued MB",overlaying="y",side="right",rangemode="tozero",showgrid=False))
    return f


def evidence_zip(results, packets, tracks, meta, comparison=None):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,df in [("simulation_results_v3.csv",results),("packet_log_v3.csv",packets),("orbit_tracks_v3.csv",tracks),("scenario_summary_v3.csv",pd.DataFrame([engine.summarize(results,packets)]))]:
            z.writestr(name,df.to_csv(index=False))
        z.writestr("model_metadata_v3.json",json.dumps(meta,indent=2,allow_nan=False))
        if comparison is not None:
            z.writestr("architecture_comparison.csv",comparison.to_csv(index=False))
    return buffer.getvalue()


with st.sidebar:
    st.markdown("## Mission parameters")
    st.caption("Each control changes the same model used by the map and KPIs.")
    fleet=st.selectbox("Synthetic fleet",[12,30,48],key="fleet")
    arch=st.selectbox("Payload architecture",list(ARCH_LABELS),format_func=ARCH_LABELS.get,key="architecture")
    topology=st.selectbox("Candidate ISL topology",list(TOPOLOGY_LABELS),format_func=TOPOLOGY_LABELS.get,key="topology",help="Bent-pipe does not switch packets over ISLs in this reference design.")
    terminal=st.selectbox("Offshore terminal",list(engine.TERMINALS),key="terminal")
    traffic=st.radio("Traffic to inspect",["Critical alarm","Routine telemetry"],key="traffic")
    local=st.toggle("Local NL gateway eligible",value=False,key="local",help="Combined scenario gate: operational and permitted. Does not guarantee line of sight.")
    alternative=st.toggle("Alternative LU gateway eligible",value=True,key="alternative",help="Hypothetical gateway, not a claim about an OQ site or licence.")
    view=st.radio("Map view",["North Sea map","Global map","3D globe"],key="view")
    with st.expander("Model assumptions"):
        duration=st.selectbox("Simulation duration (minutes)",[90,180,360],index=1)
        deadline=st.number_input("Alarm target (ms)",min_value=10.0,max_value=1000.0,value=150.0,step=10.0)
        buffer_enabled=st.checkbox("Assume onboard store-and-forward support",value=True,help="Requires established sessions and explicit payload support. Used only for the full gNB design.")
        forecast_guard=st.checkbox("Check future contacts before storing onboard",value=True,help="Keep data at the terminal unless the satellite has an earlier modeled egress before the deadline. Uses the known synthetic horizon, without reserving future capacity.")
        st.caption("550 km · 87° inclination · 10° elevation mask · 30-second samples. Remaining assumptions are in the evidence export.")

config=engine.Config(fleet_size=fleet,architecture=arch,isl_topology=topology,terminal=terminal,local_enabled=local,alternative_enabled=alternative,duration_min=duration,alarm_deadline_ms=deadline,allow_onboard_store=buffer_enabled,forecast_storage_guard=forecast_guard)
with st.spinner("Computing contact geometry and packet queues…"):
    results,packets,tracks,meta=run_model(asdict(config),engine.code_fingerprint())
summary=engine.summarize(results,packets)
maximum=float(results.time_min.max())
if "clock" not in st.session_state or st.session_state.clock > maximum:
    available=results[results.route_available]
    st.session_state.clock=float(available.iloc[0].time_min if len(available) else 0)
with st.sidebar:
    st.markdown("### Inspect the replay")
    st.slider("Simulation minute",0.0,maximum,step=.5,key="clock")
    b1,b2=st.columns(2)
    b1.button("← Previous",on_click=advance,args=(-.5,maximum),width="stretch")
    b2.button("Next →",on_click=advance,args=(.5,maximum),width="stretch")
    for label,mask,mode in [
        ("Find a direct path",results.route_kind.eq("Direct feeder"),"Critical alarm"),
        ("Find an ISL path",results.route_kind.eq("ISL relay"),"Critical alarm"),
        ("Find an onboard queue",results.telemetry_state.eq("queued_onboard"),"Routine telemetry"),
        ("Find a coverage gap",~results.terminal_visible,"Critical alarm")]:
        candidates=results[mask]
        st.button(label,disabled=candidates.empty,on_click=jump,args=(float(candidates.iloc[0].time_min) if len(candidates) else 0,mode),width="stretch")
    st.caption("Disabled search buttons mean that case does not occur in this run.")

row=results.loc[np.isclose(results.time_min,st.session_state.clock)].iloc[0]
critical=traffic=="Critical alarm"
edges=json.loads(row.route_edges if critical else row.telemetry_action_edges)
if critical:
    status={"delivered_within_target":"MODEL TARGET MET","deadline_missed":"DEADLINE MISSED","unavailable":"NO ELIGIBLE PATH"}[row.alarm_status]
    tone="green" if row.alarm_deadline_met else "red"
    reason=row.decision_reason
else:
    status={"delivered":"DELIVERED IN THIS SAMPLE","queued_ground":"QUEUED AT THE TERMINAL","queued_onboard":"QUEUED ONBOARD","overflow_ground":"TERMINAL BUFFER FULL"}.get(row.telemetry_state,row.telemetry_state.upper())
    tone="green" if row.telemetry_state=="delivered" else "red" if "overflow" in row.telemetry_state else "amber"
    reason=f"New telemetry packet {row.telemetry_packet_id}: {row.telemetry_state.replace('_',' ')}. Buffers shown include earlier packets."

st.markdown("<div class='brandline'><div class='brand'>✦ LYNQ <span>NTN-PULSE</span></div><div class='mission-chip'>OQ ANYPOINT-NTN · MODEL 3.0</div></div><div class='hero'>Every signal, the right path.</div><div class='sub'>North Sea offshore energy · regenerative NTN policy demonstrator</div>",unsafe_allow_html=True)
st.markdown("<div class='explain'><b>Synthetic simulation:</b> geometry and queues are calculated. Link rates, processing delays and payload support are assumptions. No OQ flight validation or completed MeluXina run is claimed.</div>",unsafe_allow_html=True)
chain=[edges[0]["a"]]+[e["b"] for e in edges] if edges else [terminal,"No transfer at this sample"]
if edges and edges[-1]["b"] in engine.GATEWAYS:
    chain.append("EU core / application (assumed)")
chain_html="<div class='pipe-arrow'>→</div>".join(f"<div class='pipe-node'>{escape(n)}</div>" for n in chain)
st.markdown(f"<div class='pipeline-wrap'><div class='pipe-header'><div class='pipe-title'>DECISION AT T+{row.time_min:.1f} MIN</div><div class='pipe-badge {tone}'>{status}</div></div><div class='pipe-grid'>{chain_html}</div><div class='note' style='margin-top:.7rem'>{escape(reason)}</div></div>",unsafe_allow_html=True)

m1,m2,m3,m4=st.columns(4)
m1.metric("Alarm delay at this sample",fmt(row.latency_ms,1," ms"),help="One-way propagation + packet serialization + assumed processing. Blank when no path exists.")
m2.metric("Telemetry at terminal",fmt(row.ground_queue_mb,2," MB"))
m3.metric("Telemetry in orbit",fmt(row.onboard_queue_mb,2," MB"),help="Total across distinct satellite buffers, not a single satellite's buffer.")
m4.metric("Alarm target met across run",fmt(summary["alarm_target_success_pct"],1,"%"),help="Fraction of sampled alarm probes. Not continuous coverage, a flight SLA or measured availability.")

left,right=st.columns([2.3,1.05],gap="large")
with left:
    st.markdown("### Constellation and selected transfer")
    st.caption("Move the time slider to update the entire dashboard. Lines show the selected packet’s actual modeled transfer; orange circles mark satellites retaining older telemetry.")
    st.plotly_chart(map_figure(tracks,row,config,view,edges,meta),width="stretch",config=dict(displayModeBar=False,scrollZoom=True))
    st.caption("Satellite dots are ground projections. Line positions are schematic on the map; lengths come from 3D geometry. The geographic basemap may require internet.")
    st.plotly_chart(timeline_figure(results,row.time_min,deadline),width="stretch",config=dict(displayModeBar=False))
    st.caption("Gaps in the cyan curve mean no route. Blue = terminal backlog; amber = packets retained on specific satellites.")
with right:
    st.markdown("### Decision details")
    st.markdown(f"<div class='card'><div class='label'>Geometry at this sample</div><div class='value'>{escape(row.serving_satellite or 'No access satellite')}</div><div class='note'>Elevation: <b>{fmt(row.service_elevation_deg,1,'°')}</b><br>Slant range: <b>{fmt(row.service_slant_range_km,1,' km')}</b><br>Received Doppler at {config.service_carrier_ghz:g} GHz: <b>{fmt(row.received_doppler_hz,0,' Hz')}</b><br>One-way service propagation: <b>{fmt(row.timing_advance_oneway_ms,2,' ms')}</b></div></div>",unsafe_allow_html=True)
    st.caption("Doppler is estimated from range rate. Transmit pre-compensation has the opposite sign. This does not implement a modem or 3GPP timing procedure.")
    st.markdown(f"<div class='card'><div class='label'>Alarm delay components</div><div class='note'>Propagation: <b>{fmt(row.propagation_ms,2,' ms')}</b><br>Serialization: <b>{fmt(row.serialization_ms,2,' ms')}</b><br>Assumed RAN/core/switch processing: <b>{fmt(row.assumed_processing_ms,2,' ms')}</b><br>Gateway: <b>{escape(row.gateway or 'None')}</b></div></div>",unsafe_allow_html=True)
    st.markdown(f"<div class='card'><div class='label'>Telemetry replay outcome</div><div class='value'>{escape(row.telemetry_final_status.replace('_',' '))}</div><div class='note'>Packet: {row.telemetry_packet_id}<br>Observed generation-to-delivery time: <b>{fmt(row.telemetry_delivery_min,2,' min')}</b><br>Largest individual satellite buffer: <b>{fmt(row.largest_sat_buffer_mb,2)} / {config.onboard_buffer_mb_per_sat:g} MB</b></div></div>",unsafe_allow_html=True)
    st.caption("This outcome uses the complete replay. Pending means the horizon ends before delivery/expiry is observed; it is not a promised delivery time.")
    st.markdown(f"<div class='card'><div class='label'>Whole-run packet accounting</div><div class='note'>Generated: <b>{summary['telemetry_packets_generated']}</b><br>Delivered: <b>{summary['telemetry_packets_delivered']}</b><br>Expired: <b>{summary['telemetry_packets_expired']}</b><br>Buffer overflow: <b>{summary['telemetry_packets_overflow']}</b><br>Pending at horizon: <b>{summary['telemetry_packets_pending']}</b></div></div>",unsafe_allow_html=True)

st.markdown("### Compare architectures on identical inputs")
st.caption("Same orbits, traffic, gateways and base delay assumptions. Regeneration is not forced to win. The split-RAN case applies an assumed F1 transport budget.")
comparison_key="comparison_"+json.dumps({**asdict(config),"architecture":"all"},sort_keys=True)
if st.button("Run architecture comparison",key="compare"):
    rows=[]
    with st.spinner("Comparing the three architectures…"):
        for architecture in engine.ARCHITECTURES:
            r,p,_,_=run_model(asdict(replace(config,architecture=architecture)),engine.code_fingerprint())
            rows.append(engine.summarize(r,p))
    st.session_state[comparison_key]=pd.DataFrame(rows)
comparison=st.session_state.get(comparison_key)
if comparison is not None:
    table=comparison[["architecture","sampled_route_access_pct","alarm_target_success_pct","mean_active_path_delay_ms","telemetry_packets_delivered","telemetry_packets_expired","telemetry_packets_pending"]].rename(columns={"architecture":"Architecture","sampled_route_access_pct":"Sampled route access (%)","alarm_target_success_pct":"Alarm target met (%)","mean_active_path_delay_ms":"Mean active delay (ms)","telemetry_packets_delivered":"Telemetry delivered","telemetry_packets_expired":"Expired","telemetry_packets_pending":"Pending"})
    st.dataframe(table,hide_index=True,width="stretch")

st.download_button("Download this run and its assumptions",data=evidence_zip(results,packets,tracks,meta,comparison),file_name=f"Lynq_evidence_{fleet}sat_{arch}.zip",mime="application/zip")
with st.expander("How to explain the demo"):
    st.markdown("1. Enable a gateway and inspect a direct path. A permitted gateway must also be visible.\n2. Disable the local gateway. An alternative gateway can work for **either** architecture if the geometry allows it. Regenerative switching adds eligible ISL routes.\n3. Disable both gateways. Alarms fail; telemetry stays at the terminal or on a satellite only after a valid uplink.\n4. Compare architectures and download the inputs, packet log and model assumptions.")
with st.expander("Model limits, regulatory scope and reproducibility"):
    for assumption in meta["assumptions"]:
        st.write("• "+assumption)
    st.write(meta["regulatory_scope"])
    st.write(meta["standards_scope"])
    st.caption("Engine SHA-256: "+meta["engine_sha256"])
    st.json(meta["config"])
with st.expander("Illustrative business calculator"):
    st.caption("User-entered assumptions. Separate Lynq software economics from constellation costs. The €9M / €120 figures are the team's original illustration, not verified OQ economics.")
    b1,b2,b3=st.columns(3)
    fixed=b1.number_input("Annual fixed cost (€)",min_value=0.0,value=9000000.0,step=10000.0)
    price=b2.number_input("Annual revenue per asset (€)",min_value=0.0,value=120.0,step=10.0)
    variable=b3.number_input("Annual variable cost per asset (€)",min_value=0.0,value=0.0,step=10.0)
    contribution=price-variable
    if contribution>0:
        st.metric("Illustrative break-even assets",f"{math.ceil(fixed/contribution):,}")
        st.caption("Fixed cost ÷ (revenue per asset − variable cost per asset). Zero variable cost gives an optimistic floor. This does not include omitted capex, financing or taxes.")
    else:
        st.warning("No finite break-even: contribution per asset must be positive.")
st.caption("Team Lynq · Davoud Jokar · Ines Bouissou · Gambhir Sharma · Maryam Amini")
