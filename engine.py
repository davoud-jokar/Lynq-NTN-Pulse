"""Lynq NTN-Pulse: reproducible geometry and packet-policy demonstrator.

Synthetic circular orbits; NOT OQ ephemerides or a 3GPP PHY/RAN simulator.
Run `python engine.py` for the three-architecture comparison and CSV evidence.
The dashboard calls the same functions directly and never loads legacy v2 CSVs.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_VERSION = "3.1.0"
R_EARTH = 6371.0  # km; spherical Earth
MU = 398600.4418  # km^3/s^2
OMEGA = 7.2921150e-5  # rad/s
C_KM_S = 299792.458
TERMINALS = {
    "North Sea Wind Farm": {"lat": 56.35, "lon": 3.55},
    "Energy Platform Alpha": {"lat": 58.20, "lon": 1.20},
    "Barents Sea platform": {"lat": 72.00, "lon": 30.00},
    "Mid-Atlantic vessel": {"lat": 45.00, "lon": -30.00},
}
GATEWAYS = {
    "Local GW (NL)": {"lat": 51.75, "lon": 4.10},
    "Alternative GW (LU)": {"lat": 49.61, "lon": 6.13},
}
LAYOUTS = {12: (3, 1), 30: (3, 1), 48: (4, 1), 96: (8, 4)}  # fleet: (planes, Walker phase factor)
ARCHITECTURES = ("regenerative", "functional_split", "bent_pipe")
TOPOLOGIES = ("hybrid", "rf_intra_plane", "optical_cross_plane")


@dataclass(frozen=True)
class Config:
    fleet_size: int = 12
    architecture: str = "regenerative"
    isl_topology: str = "hybrid"
    terminal: str = "North Sea Wind Farm"
    local_enabled: bool = False
    alternative_enabled: bool = True
    duration_min: int = 180
    step_s: int = 30
    altitude_km: float = 550.0
    inclination_deg: float = 87.0
    min_elevation_deg: float = 10.0
    isl_clearance_km: float = 80.0
    max_isl_range_km: float = 5000.0
    optical_links_per_sat: int = 2
    service_rate_mbps: float = 0.01
    feeder_rate_mbps: float = 10.0
    rf_rate_mbps: float = 4.0
    optical_rate_mbps: float = 100.0
    ran_processing_ms: float = 20.0
    core_network_ms: float = 20.0
    switch_ms: float = 1.0
    split_transport_budget_ms: float = 20.0  # scenario F1 transport target, not a 3GPP limit
    split_transport_pdu_bytes: int = 1500
    service_carrier_ghz: float = 2.0  # calculation frequency, not a licensed band claim
    alarm_bytes: int = 200
    alarm_deadline_ms: float = 2000.0
    telemetry_mb_per_min: float = 0.01
    telemetry_deadline_min: float = 90.0
    ground_buffer_mb: float = 64.0
    onboard_buffer_mb_per_sat: float = 64.0
    allow_onboard_store: bool = True  # assumes established session + explicit payload support
    forecast_storage_guard: bool = True

    def __post_init__(self):
        if self.fleet_size not in LAYOUTS:
            raise ValueError("Choose a synthetic 12, 30, 48 or 96 satellite design.")
        if self.architecture not in ARCHITECTURES or self.isl_topology not in TOPOLOGIES:
            raise ValueError("Unknown architecture or topology.")
        if self.terminal not in TERMINALS:
            raise ValueError("Unknown terminal.")
        positive = [self.duration_min, self.step_s, self.altitude_km, self.service_rate_mbps,
                    self.feeder_rate_mbps, self.rf_rate_mbps, self.optical_rate_mbps,
                    self.alarm_deadline_ms, self.telemetry_deadline_min, self.ground_buffer_mb,
                    self.onboard_buffer_mb_per_sat, self.telemetry_mb_per_min]
        if min(positive) <= 0 or not 0 <= self.min_elevation_deg < 90:
            raise ValueError("Durations, capacities and rates must be positive; elevation must be 0–89 degrees.")
        if self.step_s > self.duration_min * 60:
            raise ValueError("Sampling step exceeds the simulation window.")


def code_fingerprint() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def ground_xyz(lat: float, lon: float) -> np.ndarray:
    la, lo = np.radians([lat, lon])
    return R_EARTH * np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def circular_positions(c: Config, seconds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Circular two-body positions in ECEF. Synthetic epoch: ECI=ECEF at t=0."""
    planes, phase = LAYOUTS[c.fleet_size]
    per = c.fleet_size // planes
    p = np.repeat(np.arange(planes), per)
    slot = np.tile(np.arange(per), planes)
    radius = R_EARTH + c.altitude_km
    raan = np.pi * p / planes  # Walker-star: near-polar planes spread over 180 deg
    u = 2 * np.pi * slot / per + 2 * np.pi * phase * p / c.fleet_size
    u = u + np.asarray(seconds).reshape(-1, 1) * np.sqrt(MU / radius ** 3)
    inc = np.radians(c.inclination_deg)
    x = radius * (np.cos(raan) * np.cos(u) - np.sin(raan) * np.sin(u) * np.cos(inc))
    y = radius * (np.sin(raan) * np.cos(u) + np.cos(raan) * np.sin(u) * np.cos(inc))
    z = radius * np.sin(u) * np.sin(inc)
    a = OMEGA * np.asarray(seconds).reshape(-1, 1)
    xyz = np.stack((np.cos(a) * x + np.sin(a) * y,
                    -np.sin(a) * x + np.cos(a) * y, z), axis=-1)
    return xyz, p + 1


def look_angles(sats: np.ndarray, point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    delta = sats - point
    distance = np.linalg.norm(delta, axis=-1)
    elevation = np.degrees(np.arcsin(np.clip((delta @ (point / R_EARTH)) / distance, -1, 1)))
    return elevation, distance


def clear_isl(a: np.ndarray, b: np.ndarray, c: Config) -> bool:
    delta = b - a
    squared = float(delta @ delta)
    if squared <= 1e-12 or math.sqrt(squared) > c.max_isl_range_km:
        return False
    f = np.clip(-float(a @ delta) / squared, 0.0, 1.0)
    return bool(np.linalg.norm(a + f * delta) >= R_EARTH + c.isl_clearance_km)


def _edge(a: str, b: str, kind: str, distance: float, rate: float) -> dict:
    return {"a": a, "b": b, "kind": kind, "distance_km": float(distance), "rate_mbps": float(rate)}


def edge_delay_ms(edge: dict, size_mb: float) -> float:
    return edge["distance_km"] / C_KM_S * 1000 + size_mb * 8 / edge["rate_mbps"] * 1000


def snapshot(c: Config, xyz: np.ndarray, planes: np.ndarray, velocity: np.ndarray | None = None) -> dict:
    """Physical contact graph plus scenario permission gates; no forced fleet bonus."""
    names = [f"LYNQ-{i + 1:02d}" for i in range(len(xyz))]
    terminal = ground_xyz(**TERMINALS[c.terminal])
    elevations, ranges = look_angles(xyz, terminal)
    gw_looks = {k: look_angles(xyz, ground_xyz(**v)) for k, v in GATEWAYS.items()}
    graph = {n: [] for n in names}
    candidates = []
    for i in range(len(xyz)):
        for j in range(i + 1, len(xyz)):
            if not clear_isl(xyz[i], xyz[j], c):
                continue
            distance = float(np.linalg.norm(xyz[j] - xyz[i]))
            if planes[i] == planes[j] and c.isl_topology in ("rf_intra_plane", "hybrid"):
                plane_members = np.flatnonzero(planes == planes[i]).tolist()
                gap = abs(plane_members.index(i) - plane_members.index(j))
                if gap in (1, len(plane_members) - 1):
                    e = _edge(names[i], names[j], "RF ISL", distance, c.rf_rate_mbps)
                    graph[names[i]].append(e)
                    graph[names[j]].append(_edge(names[j], names[i], e["kind"], distance, e["rate_mbps"]))
            elif abs(int(planes[i]) - int(planes[j])) == 1 and c.isl_topology in ("optical_cross_plane", "hybrid"):
                candidates.append((distance, i, j))
    # Deterministic candidate optical contacts, at most N terminals per satellite.
    degree = np.zeros(len(xyz), dtype=int)
    for distance, i, j in sorted(candidates):
        if degree[i] >= c.optical_links_per_sat or degree[j] >= c.optical_links_per_sat:
            continue
        degree[i] += 1
        degree[j] += 1
        graph[names[i]].append(_edge(names[i], names[j], "Optical ISL", distance, c.optical_rate_mbps))
        graph[names[j]].append(_edge(names[j], names[i], "Optical ISL", distance, c.optical_rate_mbps))
    enabled = dict(zip(GATEWAYS, (c.local_enabled, c.alternative_enabled)))
    for gateway, (elev, distance) in gw_looks.items():
        if enabled[gateway]:
            for i in np.flatnonzero(elev >= c.min_elevation_deg):
                graph[names[i]].append(_edge(names[i], gateway, "Feeder", distance[i], c.feeder_rate_mbps))
    return {"names": names, "xyz": xyz, "velocity": velocity, "planes": planes,
            "terminal_xyz": terminal, "elevation": elevations, "range": ranges,
            "gateway_looks": gw_looks, "graph": graph}


def path_from_sat(c: Config, s: dict, source: str, size_mb: float) -> list[dict] | None:
    """Lowest modeled transport delay. Bent-pipe considers every eligible gateway."""
    heap = [(0.0, source, [])]
    best = {source: 0.0}
    while heap:
        cost, node, route = heapq.heappop(heap)
        if cost > best.get(node, math.inf):
            continue
        if node in GATEWAYS:
            return route
        for e in s["graph"].get(node, []):
            if c.architecture == "bent_pipe" and e["kind"] != "Feeder":
                continue
            hop_cost = edge_delay_ms(e, size_mb)
            if "ISL" in e["kind"]:
                hop_cost += c.switch_ms
            new_cost = cost + hop_cost
            if c.architecture == "functional_split":
                # A large application file is segmented; do not apply the F1 PDU
                # transport target to the serialization of that entire file.
                f1_cost = sum(edge_delay_ms(h, c.split_transport_pdu_bytes / 1e6) +
                              (c.switch_ms if "ISL" in h["kind"] else 0) for h in route + [e])
                if f1_cost > c.split_transport_budget_ms:
                    continue
            if new_cost < best.get(e["b"], math.inf):
                best[e["b"]] = new_cost
                heapq.heappush(heap, (new_cost, e["b"], route + [e]))
    return None


def latency_parts(c: Config, edges: list[dict], size_mb: float) -> dict:
    propagation = sum(e["distance_km"] for e in edges) / C_KM_S * 1000
    serialization = sum(size_mb * 8 / e["rate_mbps"] * 1000 for e in edges)
    processing = c.ran_processing_ms + c.core_network_ms + c.switch_ms * sum("ISL" in e["kind"] for e in edges)
    return {"propagation_ms": propagation, "serialization_ms": serialization,
            "assumed_processing_ms": processing, "latency_ms": propagation + serialization + processing}


def terminal_route(c: Config, s: dict, size_mb: float) -> list[dict] | None:
    options = []
    for i in np.flatnonzero(s["elevation"] >= c.min_elevation_deg):
        source = s["names"][i]
        rest = path_from_sat(c, s, source, size_mb)
        if rest is not None:
            edges = [_edge(c.terminal, source, "Service", s["range"][i], c.service_rate_mbps)] + rest
            options.append((latency_parts(c, edges, size_mb)["latency_ms"], source, edges))
    return min(options, key=lambda q: (q[0], q[1]))[2] if options else None


def route_json(edges: list[dict] | None) -> str:
    return json.dumps(edges or [], separators=(",", ":"))


def decide_alarm(c: Config, s: dict) -> dict:
    route = terminal_route(c, s, c.alarm_bytes / 1e6)
    visible = bool(np.any(s["elevation"] >= c.min_elevation_deg))
    nearest = int(np.argmax(s["elevation"])) if visible else None
    if route:
        serving = route[0]["b"]
        parts = latency_parts(c, route, c.alarm_bytes / 1e6)
        meets = parts["latency_ms"] <= c.alarm_deadline_ms
        state = "delivered_within_target" if meets else "deadline_missed"
        reason = "Eligible geometric route meets the assumed delay budget." if meets else "Route exists, but its modeled delay exceeds the alarm deadline."
    else:
        serving = s["names"][nearest] if nearest is not None else ""
        parts = {k: None for k in ("propagation_ms", "serialization_ms", "assumed_processing_ms", "latency_ms")}
        state, meets = "unavailable", False
        reason = "No satellite above the elevation mask." if not visible else "No eligible end-to-end path under geometry, permissions and architecture constraints."
    return {"terminal_visible": visible, "serving_satellite": serving, "route_available": bool(route),
            "alarm_status": state, "alarm_deadline_met": meets, "decision_reason": reason,
            "gateway": route[-1]["b"] if route else "", "route_kind": ("ISL relay" if any("ISL" in e["kind"] for e in route or []) else "Direct feeder") if route else "No path",
            "route_edges": route_json(route), **parts}


def _link_key(e: dict) -> tuple[str, str]:
    return tuple(sorted((e["a"], e["b"])))


def simulate(c: Config) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """One terminal, deterministic sampled contacts and conserved telemetry packets.

    Each sample emits one alarm probe and one telemetry packet. Pending telemetry
    stays on its actual satellite or terminal. No inter-step queue teleportation.
    Contacts are frozen within a step; no fading, HARQ or acquisition is modeled.
    """
    times = np.arange(0, c.duration_min * 60, c.step_s, dtype=float)
    positions, planes = circular_positions(c, times)
    plus, _ = circular_positions(c, times + 0.25)
    minus, _ = circular_positions(c, times - 0.25)
    velocities = (plus - minus) / 0.5
    packet_mb = c.telemetry_mb_per_min * c.step_s / 60
    states = [snapshot(c, positions[k], planes, velocities[k]) for k in range(len(times))]
    bulk_routes = [terminal_route(c, s, packet_mb) for s in states]
    # Contact-aware storage: do not strand a packet on a satellite if waiting at
    # the terminal has an earlier modeled opportunity. Future capacity is not
    # reserved: this is a planning bound, never a delivery promise.
    next_ground = np.full(len(times) + 1, np.inf)
    next_exit = np.full((len(times) + 1, c.fleet_size), np.inf)
    if c.architecture == "regenerative" and c.allow_onboard_store and c.forecast_storage_guard:
        for k in range(len(times) - 1, -1, -1):
            next_ground[k] = next_ground[k + 1]
            if bulk_routes[k]:
                next_ground[k] = min(next_ground[k], times[k] + latency_parts(c, bulk_routes[k], packet_mb)["latency_ms"] / 1000)
            next_exit[k] = next_exit[k + 1]
            for i, sat in enumerate(states[k]["names"]):
                route = path_from_sat(c, states[k], sat, packet_mb)
                if route:
                    next_exit[k, i] = min(next_exit[k, i], times[k] + latency_parts(c, route, packet_mb)["latency_ms"] / 1000)
    packets, records, track_rows = [], [], []
    generated = delivered = expired = overflow = 0.0
    for k, t in enumerate(times):
        s = states[k]
        decision = decide_alarm(c, s)
        for i, name in enumerate(s["names"]):
            x, y, z = positions[k, i]
            track_rows.append({"fleet_size": c.fleet_size, "time_min": t / 60, "plane": int(planes[i]),
                               "satellite": name, "lat": float(np.degrees(np.arcsin(z / np.linalg.norm(positions[k, i])))),
                               "lon": float(np.degrees(np.arctan2(y, x))), "altitude_km": c.altitude_km,
                               "x_km": x, "y_km": y, "z_km": z})
        for packet in packets:
            if packet["status"] == "pending" and t >= packet["deadline_s"]:
                packet.update(status="expired", final_time_s=packet["deadline_s"])
                expired += packet["size_mb"]
        pending = [p for p in packets if p["status"] == "pending"]
        ground_mb = sum(p["size_mb"] for p in pending if p["location"] == "ground")
        new = {"packet_id": f"T-{k:05d}", "born_s": t, "size_mb": packet_mb,
               "deadline_s": t + c.telemetry_deadline_min * 60, "location": "ground", "uploaded_s": None,
               "status": "pending", "delivered_s": None, "final_time_s": None, "delivery_route": "[]"}
        generated += packet_mb
        if ground_mb + packet_mb > c.ground_buffer_mb + 1e-9:
            new.update(status="overflow_ground", final_time_s=t)
            overflow += packet_mb
        packets.append(new)
        used = {}
        alarm_edges = json.loads(decision["route_edges"])
        if alarm_edges:
            for e in alarm_edges:
                used[_link_key(e)] = c.alarm_bytes / 1e6
        action_edges = []
        route_cache = {}

        def outbound(sat):
            if sat not in route_cache:
                route_cache[sat] = path_from_sat(c, s, sat, packet_mb)
            return route_cache[sat]

        def can_send(edges, size):
            if not edges or latency_parts(c, edges, size)["latency_ms"] > c.step_s * 1000:
                return False
            return all(used.get(_link_key(e), 0.0) + size <= e["rate_mbps"] * c.step_s / 8 + 1e-9 for e in edges)

        def reserve(edges, size):
            for e in edges:
                key = _link_key(e)
                used[key] = used.get(key, 0.0) + size

        # Deliver already uploaded packets before terminal backlog, FIFO in each group.
        direct_bulk = bulk_routes[k]
        waiting = sorted((p for p in packets if p["status"] == "pending"),
                         key=lambda p: (p["location"] == "ground", p["born_s"]))
        for packet in waiting:
            edges = direct_bulk if packet["location"] == "ground" else outbound(packet["location"])
            if can_send(edges, packet["size_mb"]):
                arrival = t + latency_parts(c, edges, packet["size_mb"])["latency_ms"] / 1000
                if arrival <= packet["deadline_s"]:
                    reserve(edges, packet["size_mb"])
                    packet.update(status="delivered", delivered_s=arrival, final_time_s=arrival, delivery_route=route_json(edges))
                    delivered += packet["size_mb"]
                    if packet is new:
                        action_edges = edges
                    continue
            # Full regenerative payload only, with explicitly assumed disconnected-session support.
            if packet["location"] != "ground" or c.architecture != "regenerative" or not c.allow_onboard_store:
                continue
            if direct_bulk is not None:  # keep at terminal when active path is merely capacity-limited
                continue
            for i in np.argsort(-s["elevation"]):
                if s["elevation"][i] < c.min_elevation_deg:
                    break
                sat = s["names"][i]
                if c.forecast_storage_guard:
                    earliest_exit = next_exit[k + 1, i]
                    if earliest_exit > packet["deadline_s"] or earliest_exit >= next_ground[k + 1]:
                        continue
                occupied = sum(p["size_mb"] for p in packets if p["status"] == "pending" and p["location"] == sat)
                uplink = [_edge(c.terminal, sat, "Service", s["range"][i], c.service_rate_mbps)]
                if occupied + packet["size_mb"] <= c.onboard_buffer_mb_per_sat + 1e-9 and can_send(uplink, packet["size_mb"]):
                    arrival = t + edge_delay_ms(uplink[0], packet["size_mb"]) / 1000
                    if arrival > packet["deadline_s"]:
                        continue
                    reserve(uplink, packet["size_mb"])
                    packet.update(location=sat, uploaded_s=arrival)
                    if packet is new:
                        action_edges = uplink
                    break
        pending = [p for p in packets if p["status"] == "pending"]
        ground_mb = sum(p["size_mb"] for p in pending if p["location"] == "ground")
        onboard_mb = sum(p["size_mb"] for p in pending if p["location"] != "ground")
        occupied = {n: sum(p["size_mb"] for p in pending if p["location"] == n) for n in s["names"]}
        phase = new["status"] if new["status"] != "pending" else ("queued_ground" if new["location"] == "ground" else "queued_onboard")
        row = {"model_version": MODEL_VERSION, "fleet_size": c.fleet_size, "architecture": c.architecture,
               "isl_topology": c.isl_topology, "terminal": c.terminal, "local_enabled": c.local_enabled,
               "alternative_enabled": c.alternative_enabled, "time_min": t / 60,
               **decision, "telemetry_packet_id": new["packet_id"], "telemetry_state": phase,
               "telemetry_location": new["location"], "telemetry_action_edges": route_json(action_edges),
               "ground_queue_mb": ground_mb, "onboard_queue_mb": onboard_mb,
               "largest_sat_buffer_mb": max(occupied.values()), "onboard_queue_by_sat": json.dumps({n: round(v, 6) for n, v in occupied.items() if v > 0}),
               "generated_mb": generated, "delivered_mb": delivered, "expired_mb": expired, "overflow_mb": overflow}
        sat = decision["serving_satellite"]
        if sat:
            i = s["names"].index(sat)
            delta = s["xyz"][i] - s["terminal_xyz"]
            rr = float(delta @ velocities[k, i] / s["range"][i])
            row.update(service_slant_range_km=float(s["range"][i]), service_elevation_deg=float(s["elevation"][i]),
                       service_range_rate_km_s=rr, received_doppler_hz=-rr / C_KM_S * c.service_carrier_ghz * 1e9,
                       timing_advance_oneway_ms=float(s["range"][i] / C_KM_S * 1000))
        else:
            row.update({k: None for k in ("service_slant_range_km", "service_elevation_deg", "service_range_rate_km_s", "received_doppler_hz", "timing_advance_oneway_ms")})
        records.append(row)
    packet_df = pd.DataFrame(packets)
    for row, packet in zip(records, packets):
        row["telemetry_final_status"] = packet["status"]
        row["telemetry_delivery_min"] = (packet["delivered_s"] - packet["born_s"]) / 60 if packet["status"] == "delivered" else None
    # Forward-looking contact window uses sampled route geometry, not an invented ETA.
    next_time = None
    for row in reversed(records):
        if row["route_available"]:
            next_time = row["time_min"]
        row["next_route_sample_min"] = next_time
    return pd.DataFrame(records), packet_df, pd.DataFrame(track_rows), metadata(c)


def summarize(results: pd.DataFrame, packets: pd.DataFrame) -> dict:
    last = results.iloc[-1]
    delivered = packets[packets.status == "delivered"]
    delays = (delivered.delivered_s - delivered.born_s) / 60
    return {"fleet_size": int(last.fleet_size), "architecture": last.architecture,
            "isl_topology": last.isl_topology, "terminal": last.terminal,
            "local_enabled": bool(last.local_enabled), "alternative_enabled": bool(last.alternative_enabled),
            "sampled_terminal_access_pct": float(100 * results.terminal_visible.mean()),
            "sampled_route_access_pct": float(100 * results.route_available.mean()),
            "alarm_target_success_pct": float(100 * results.alarm_deadline_met.mean()),
            "mean_active_path_delay_ms": float(results.latency_ms.mean()) if results.latency_ms.notna().any() else None,
            "telemetry_packets_generated": len(packets), "telemetry_packets_delivered": len(delivered),
            "telemetry_packets_pending": int((packets.status == "pending").sum()),
            "telemetry_packets_expired": int((packets.status == "expired").sum()),
            "telemetry_packets_overflow": int(packets.status.str.startswith("overflow").sum()),
            "mean_delivered_telemetry_delay_min": float(delays.mean()) if len(delays) else None,
            "max_onboard_queue_mb": float(results.onboard_queue_mb.max()),
            "max_ground_queue_mb": float(results.ground_queue_mb.max()),
            "mass_balance_error_mb": float(last.generated_mb - last.delivered_mb - last.expired_mb - last.overflow_mb - last.ground_queue_mb - last.onboard_queue_mb)}


def metadata(c: Config) -> dict:
    central = np.arccos(R_EARTH / (R_EARTH + c.altitude_km) * np.cos(np.radians(c.min_elevation_deg))) - np.radians(c.min_elevation_deg)
    return {"project": "Lynq NTN-Pulse", "model_version": MODEL_VERSION, "engine_sha256": code_fingerprint(),
            "status": "Synthetic geometry and packet-policy demonstrator; not OQ-validated",
            "config": asdict(c), "planes": LAYOUTS[c.fleet_size][0], "phase_factor": LAYOUTS[c.fleet_size][1],
            "synthetic_epoch": "ECI and ECEF aligned at t=0; no real observation date",
            "footprint_ground_radius_km": float(R_EARTH * central),
            "assumptions": [
                "Circular two-body orbits, rotating spherical Earth, no perturbations or terrain masks.",
                "Walker-star layouts (planes spread over 180 deg): 12 = 3x4 (today-scale), 48 = 4x12 (OQ Gen-2 size), 96 = 8x12. Synthetic, not confirmed OQ orbital slots.",
                "Links require elevation/clearance/range and scenario permissions. These are geometric candidate links, not verified RF/optical link budgets.",
                "RF links join neighbouring slots in one plane; optical contacts use nearest feasible cross-plane pairs with a degree cap. PAT time and optical weather are excluded.",
                "All architectures use identical orbit geometry, service rates, gateway permissions and base processing assumptions. Bent-pipe can choose either eligible visible gateway.",
                "Functional split adds an assumed F1 transport budget; it has no autonomous upper-layer onboard queue in this model.",
                "Onboard store-and-forward assumes an established device session, authentication continuity and explicit payload support. A gNB alone does not provide a complete disconnected 5G Core.",
                "One terminal workload per run; shared multi-terminal traffic and congestion are excluded. Links are frozen during each sampling step.",
                "One alarm probe and one telemetry packet per sample. Alarms reserve capacity first. Buffers retain the actual satellite identity; packets never migrate during a serving-node change.",
                "Contact-aware buffering uses the known synthetic horizon: upload only if that satellite has an earlier modeled egress than waiting at the terminal, before the packet deadline. This optimistic planning bound does not reserve future link capacity.",
                "Latency is propagation + serialization + declared processing/core assumptions. No NR scheduling, HARQ, fading, modem, handover or acquisition simulation.",
                "Telemetry outcomes are replay results. Pending packets are right-censored at the simulation horizon; next contact is not a delivery guarantee.",
                "Gateway locations and permission toggles are hypothetical. No ITU, GDPR or national licensing certification is performed.",
            ],
            "regulatory_scope": "A future compliance review must assess Article 9 coordination, applicable Article 21 PFD and Article 22 EPFD, national service rights and GDPR roles/processing. Permission toggles are scenario inputs only.",
            "standards_scope": "3GPP Rel-17/18/19 feature mapping remains engineering work; this app does not implement or certify those releases.",
            "sources": ["https://gssc.esa.int/navipedia/index.php/Transformations_between_ECEF_and_ENU_coordinates",
                        "https://www.itu.int/epfdsupport/",
                        "https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest"]}


def write_evidence(output: Path, configs: list[Config]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    results, packets, tracks, summaries, meta = [], [], [], [], []
    for index, c in enumerate(configs):
        r, p, tr, m = simulate(c)
        case = f"case_{index:03d}"
        results.append(r.assign(scenario_id=case))
        packets.append(p.assign(scenario_id=case, architecture=c.architecture, fleet_size=c.fleet_size, isl_topology=c.isl_topology))
        tracks.append(tr.assign(scenario_id=case))
        summaries.append({"scenario_id": case, **summarize(r, p)})
        meta.append({"scenario_id": case, **m})
        print(f"{case}: {c.fleet_size} / {c.architecture} / {c.isl_topology}", flush=True)
    pd.concat(results, ignore_index=True).to_csv(output / "simulation_results_v3.csv", index=False)
    pd.concat(packets, ignore_index=True).to_csv(output / "packet_log_v3.csv", index=False)
    pd.concat(tracks, ignore_index=True).to_csv(output / "orbit_tracks_v3.csv", index=False)
    pd.DataFrame(summaries).to_csv(output / "scenario_summary_v3.csv", index=False)
    (output / "model_metadata_v3.json").write_text(json.dumps(meta, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Evidence saved in {output.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "data_v3")
    parser.add_argument("--fleet", type=int, choices=tuple(LAYOUTS), default=12)
    parser.add_argument("--duration-min", type=int, default=180)
    parser.add_argument("--step-s", type=int, default=30)
    parser.add_argument("--sweep", action="store_true", help="Compare all 27 fleet/architecture/topology combinations.")
    args = parser.parse_args()
    base = Config(fleet_size=args.fleet, duration_min=args.duration_min, step_s=args.step_s)
    configs = [replace(base, architecture=a) for a in ARCHITECTURES]
    if args.sweep:
        configs = [replace(base, fleet_size=f, architecture=a, isl_topology=t) for f in LAYOUTS for a in ARCHITECTURES for t in TOPOLOGIES]
    write_evidence(args.output, configs)


if __name__ == "__main__":
    main()
