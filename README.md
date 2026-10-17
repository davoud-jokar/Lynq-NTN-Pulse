# Lynq NTN-Pulse — model 3.1

Team Lynq: Davoud Jokar, Ines Bouissou, Gambhir Sharma, Maryam Amini.

A dark Streamlit dashboard and a reproducible, **synthetic geometry and packet-policy model** for the NeoSpace / OQ AnyPoint-NTN challenge. This is a replacement for the uploaded v2 demonstrator, not a flight-qualified digital twin or a 3GPP implementation.

## Run locally

Tested with Python 3.12. Use a virtual environment in PyCharm or your terminal.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The dashboard computes through `engine.py`. It does **not** require `engine.py` to be run first, and never reads the old v2 CSVs. Streamlit caches runs with the configuration and engine source hash. The included `.streamlit/config.toml` sets the dark theme. All data and computations are local; Plotly's geographic basemap may need an internet connection.

## What was repaired

| Uploaded v2 issue | v3 behavior |
|---|---|
| Sinusoidal tracks called Walker orbits; forced visibility by fleet and timestamp | Circular two-body orbits on a rotating spherical Earth; elevation and slant range from ECEF geometry |
| 48-satellite visibility forced to `True` | No fleet has guaranteed access; gaps emerge from geometry |
| Bent-pipe always failed when the local gateway was blocked | Any visible, eligible gateway can serve the transparent architecture |
| Relay chosen by nearest gateway, without checking a connected path | Explicit ISL graph, Earth clearance, range, plane rules and optical degree cap |
| Added intermediate map point presented as a satellite hop | Only actual satellite identifiers and selected graph edges are drawn |
| Latency had fleet bonuses and mixed surface distance with slant range | One-way propagation + packet serialization + declared processing assumptions |
| Arbitrary SNR and handover metrics | Removed; range/range-rate, modeled Doppler and delay components are exposed |
| Bulk traffic was always labeled onboard-buffered, even without an uplink | Packets stay at the terminal until a valid transfer; onboard buffers retain satellite identity |
| Queue could drain without a delivery path | Each transfer requires a valid route and per-link byte capacity; expiry and overflow are counted |
| Nearest serving-node changes implicitly moved stored data | Stored packets remain on their upload satellite until delivered or expired |
| Plotly autoplay moved the map while external KPIs stayed frozen | A single Streamlit timestamp updates routes, queues, charts and KPIs together |
| Static €9M / 75k-asset outcome | Explicit cost/revenue inputs and contribution-margin break-even formula |
| Old datasets could silently survive code changes | The app calls the current engine; v3 evidence exports carry inputs and code hash |

## Scope and assumptions

- Walker-star shells (planes spread over 180°): 12 = 3×4 (today scale), 48 = 4×12 (OQ Gen-2 size), 96 = 8×12; 550 km, 87°. At 550 km an in-plane RF ring needs ≥9 satellites per plane, so only 48 and 96 close rings. Optical cross-plane links connect adjacent planes only (none across the counter-rotating seam). Synthetic layouts, not confirmed OQ orbital slots.
- Epoch: ECI and ECEF aligned at t=0; no claimed observation date. The Earth radius is 6371 km, gravitational parameter 398600.4418 km³/s², rotation 7.2921150e-5 rad/s. No perturbations, atmosphere or terrain.
- A ground contact requires elevation ≥10°. ISLs require ≤5000 km and a chord clearing Earth by ≥80 km. RF joins adjacent slots in a plane. Optical links join the nearest eligible cross-plane pairs with at most two optical contacts per satellite. Pointing/acquisition, hardware duty cycles, power and link margins are not modeled.
- The two gateways and permission toggles are hypothetical. Eligibility combines assumed operating permission and operational status; geometry is checked separately. The full 5G core remains on the ground.
- All architectures share the same service/feeder rates and base RAN/core processing costs. Regenerative processing does not receive a hard-coded latency or availability advantage. Split RAN has a configurable 20 ms F1 transport target for a 1500-byte reference PDU, an engineering scenario assumption rather than a universal 3GPP requirement.
- Default link rates: service 0.01 Mbps (NB-IoT-class standard module), feeder 10 Mbps, RF ISL 4 Mbps, optical 100 Mbps. RAN processing 20 ms, core/IP processing 20 ms, ISL switching 1 ms/hop. These assumptions require OQ review. The 2 GHz Doppler calculation frequency is not a licence or band-allocation claim.
- Model sampling is 30 seconds. Contacts remain frozen during each sample. The model probes one 200-byte alarm (2 s target) and generates one telemetry packet per step, corresponding to 0.01 MB/min, with a 90-minute telemetry deadline. MB is decimal, 1 MB = 1,000,000 bytes.
- One terminal workload per run. There is no multi-terminal traffic contention, fading, HARQ, beam scheduling, modem, authentication handshake, handover interruption or detailed RF/optical link-budget model. Candidate routes are optimistic transport scenarios, not demonstrated service availability.
- Each transfer reserves byte capacity on all used links for that time step. Alarms have priority; older onboard telemetry is serviced before terminal backlog. Packets are atomic application messages in this simplified model.
- Only the full regenerative case may buffer onboard, and only when the corresponding option is enabled. This assumes an already established session, authentication continuity and supported payload storage. A gNB alone does not supply a complete disconnected core.
- The default storage guard uses the known synthetic contact horizon. A packet is uploaded for storage only if its satellite has an earlier modeled egress than remaining at the terminal, before its deadline. This planning bound ignores future competition and does not reserve capacity. Turn the guard off to study the effect of naive buffering.
- A queue retains packets on their specific satellite. When buffers fill, data remains at the terminal until that buffer overflows; expired or overflowed packets remain in the log. “Pending” at the horizon is a censored observation, not successful delivery.
- `next_route_sample_min` is the next sampled alarm-size route opportunity, not a telemetry delivery ETA. Telemetry delay reported on the screen is the eventual **replay** outcome for the packet generated at that sample.

## Three short demonstrations

1. **Alternate gateway:** select 12 satellites, bent-pipe, local gateway off, LU on; click “Find a direct path.” This explicitly shows that a blocked local gateway does not automatically defeat a transparent network.
2. **Actual ISL path:** select 48 sats · 4×12 (Gen-2), full onboard gNB, Barents Sea platform or Mid-Atlantic vessel, local off, LU on; click “Find an ISL path.” Every drawn hop is in the modeled graph. With 12 satellites (4 per plane) no in-plane ring can close, so no ISL route exists.
3. **No route and buffering:** turn both gateways off. Alarms have no delay value because delivery is unavailable. With the forecast guard on, telemetry remains at the terminal because no future gateway egress exists in that run. Restore LU and use “Find an onboard queue” to inspect a genuine modeled store-and-forward transfer.

Use the screenshot or recording you capture on your own system for the venue backup. The app does not claim a completed MeluXina benchmark.

## Export reproducible evidence

The dashboard's download button bundles the active configuration, results, tracks, packet log, summary, and an architecture comparison if requested.

```bash
python engine.py
python engine.py --fleet 48 --duration-min 180 --output results_48
python engine.py --sweep --duration-min 180 --output results_sweep
```

The default CLI compares the three architectures at one North Sea terminal, 12 satellites, hybrid topology, local gateway disabled and LU enabled. `--sweep` compares 27 fleet/architecture/topology combinations. The same CLI can be called in an allocated batch job later; it does not require an HPC allocation to run locally.

| Output | Meaning |
|---|---|
| `simulation_results_v3.csv` | One decision/queue record per time sample, with actual route edges |
| `packet_log_v3.csv` | Telemetry generation, upload, final state and delivery timestamps |
| `orbit_tracks_v3.csv` | ECEF position, subpoint and satellite identity |
| `scenario_summary_v3.csv` | Per-scenario counts and conditional delay summaries |
| `model_metadata_v3.json` | Input parameters, assumptions, version and engine SHA-256 |

The included `data_v3` is a 180-minute example for the 48-satellite (4×12) Gen-2 layout at the North Sea terminal with only the Luxembourg gateway eligible. It is not an OQ flight result.

## Validation

```bash
python -m unittest discover -s tests -v
python tests/check_dashboard.py
```

The engine suite contains 14 checks covering overhead elevation/range, orbit radius, Earth-blocked ISLs, legal alternate gateway selection, actual relay connectivity, deadline failure, per-sample byte conservation, buffer limits, expiry, overflow, satellite queue identity, no independent split/transparent onboard storage, and the forecast storage guard.

Streamlit AppTest exercised 24 architecture/gateway/traffic states, six additional fleet/topology states, all three map projections and the comparison table with no exceptions. This is an application-logic test, **not** a browser screenshot or physical validation. A browser visual check could not be completed in the build environment. Inspect the map once in your local browser before presenting, including basemap connectivity and your display size.

## Deployment

Keep `app.py`, `engine.py` and `requirements.txt` at the repository root. Include `.streamlit/config.toml`. Select `app.py` as the Streamlit Cloud entrypoint and use Python 3.12. The example CSVs and tests are optional for hosting. No credentials are needed for this demonstrator; do not commit a secrets file. This package does not change your remote GitHub repository or existing Cloud deployment automatically.

## Regulatory and standards boundary

Permission gating is not a regulatory certification. Article 9 coordination, applicable Article 21 PFD and Article 22 EPFD protections require a separate assessment for the actual bands and services. Article 22 is not a universal terrestrial-interference limit. EU hosting alone does not demonstrate GDPR compliance. 3GPP Rel-17/18/19 feature applicability and disconnected session support remain work for the OQ interface review.

References used for coordinate interpretation, deployment and testing:

- ESA Navipedia, ECEF/ENU transformation and elevation: https://gssc.esa.int/navipedia/index.php/Transformations_between_ECEF_and_ENU_coordinates
- ITU EPFD support and Article 21/22 distinction: https://www.itu.int/epfdsupport/
- Streamlit AppTest: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest
- Streamlit Community Cloud deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
