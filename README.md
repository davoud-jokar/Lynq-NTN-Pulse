# 🛰️ Lynq NTN-Pulse
**A Jurisdiction-Aware Digital Twin & Policy Engine for Regenerative 3GPP 5G NR-NTN Constellations**  
*NeoSpace Europe 2026 — Phase 2 Demonstrator (OQ Technology Challenge)*

---

## 🎯 Overview
**Lynq NTN-Pulse** is a deterministic digital-twin demonstrator designed for offshore energy corridors in the **North Sea**. It simulates how an onboard regenerative 3GPP payload (`Full gNB` or `CU/DU Functional Split`) dynamically routes industrial traffic when local ground gateways fail or violate European data sovereignty rules.

**Winning Message:** *Lynq keeps critical offshore signals moving when the local gateway cannot.*

---

## ⚙️ Key Architectural Features (Validated for Phase 2)
* **Constellation Sizing:** Parametric comparison between **12 LEO** (current baseline), **30 LEO**, and **48 LEO** (Gen-2 target) fleets.
* **3GPP Payload Split Analysis:** Evaluates onboard **Full gNB** versus **Functional Split (DU onboard / CU on ground)** alongside traditional transparent **Bent-pipe** relays.
* **ISL Trade-off & Link Budget:** Compares **RF ISL** (low SWaP, requires ITU/national spectrum licensing such as ILR) against **Optical ISL** (license-free, high capacity) and **Hybrid RF + Optical** topologies.
* **QoS Traffic Prioritization & Handover:**
  * **Critical Alarms (SOS / Shutdown):** Pre-emptive low-latency routing (~90 ms) via ISL to an authorized sovereign European gateway (Luxembourg).
  * **Bulk Telemetry:** Queued in constrained 6U CubeSat memory (**Store-and-Forward**) for the next compliant pass, modeling realistic multi-second orbital handover context transfer (~2–4 s).
* **HPC Provenance:** Calibrated and executed on the **MeluXina EuroHPC Supercomputer** (LuxProvide Project `p201621`).

---

## 🚀 Quick Start (Local & Offline Execution)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
