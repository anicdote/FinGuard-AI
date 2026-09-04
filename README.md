# FinGuard AI — Real-Time AML Compliance & Fraud Detection Platform

> **AI-assisted financial fraud detection and AML investigation platform** that turns a suspicious transaction into an evidence-backed, regulator-ready investigation — automatically.

[![Built at Smart Horizon 2026](https://img.shields.io/badge/Hackathon-Smart%20Horizon%202026-blueviolet)](#hackathon)
[![PMLA 2002](https://img.shields.io/badge/Compliance-PMLA%202002%20%2F%20FIU--IND-critical)](#solution-overview---the-six-agent-investigation-pipeline)
[![Python](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python-009688)](#tech-stack)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-61DAFB)](#tech-stack)
[![License](https://img.shields.io/badge/License-See%20ATTRIBUTIONS.md-lightgrey)](ATTRIBUTIONS.md)

---

## Problem Statement

Traditional fraud detection systems generate a single fraud probability score per transaction — but a score alone doesn't tell an investigator **why** a transaction is suspicious, **who else** is involved, or **what regulation** applies.

- Money laundering typically spans across multiple accounts and transactions, not just one.
- Evidence (behavioural patterns, watchlists, PEP matches) is scattered across disconnected systems.
- Mapping suspicious activity to **FATF typologies** and **PMLA sections** is still a manual, error-prone process.
- Investigators need a **traceable, auditable** decision trail — not a black-box score.

**FinGuard AI** solves this by wrapping fraud detection in a six-agent investigation pipeline that produces a complete, explainable, regulation-mapped case file — ready for compliance review and STR filing.

---

## Solution Overview — The Six-Agent Investigation Pipeline

FinGuard AI uses an **adaptive multi-agent architecture** where a planner decides which agents actually need to run for a given transaction, instead of a single monolithic model:

| Agent | Role |
|---|---|
| **1 — Anomaly Detection** | XGBoost + Isolation Forest ensemble generates a fraud probability with SHAP explanations |
| **2 — Evidence Gathering** | Detects suspicious behavioural patterns, screens watchlists and PEP matches |
| **3 — Network Investigation** | Analyses connected accounts and surfaces potential fraud networks |
| **4 — Regulatory Risk Assessment** | Maps evidence to FATF-style typologies and applicable PMLA sections |
| **5 — Explanation & STR Drafting** | Generates a human-readable explanation and a structured STR draft |
| **6 — Recommended Action** | Combines all signals to recommend `BLOCK`, `FILE_STR`, `ESCALATE`, `MONITOR`, `REQUEST_INFO`, or `CLOSE` |

### What makes it different

- **Multi-agent, not monolithic** — six specialised agents instead of one fraud model
- **Adaptive investigation** — agents run conditionally based on prior findings (e.g. low-risk transactions skip network analysis)
- **Evidence-driven** — decisions are backed by behavioural evidence + watchlist/PEP data, not a single score
- **Network-aware** — automatically identifies connected high-risk accounts and spins up linked sub-cases
- **Explainable by design** — SHAP values show exactly which features pushed the fraud probability up or down
- **Regulatory intelligence** — links every case to FATF typologies and PMLA sections automatically
- **Hardware-backed security** — fingerprint verification required for login and STR submission
- **Fully auditable** — every human decision, status change, and biometric attempt is logged

---

## Screenshots

> Save the hackathon deck screenshots into `docs/screenshots/` using the filenames below (or update the paths) so they render here.

### Overview — FATF Typology Mapping, Sub-Cases & SHAP Explanation
<img width="1351" height="641" alt="WhatsApp Image 2026-09-05 at 5 16 58 AM" src="https://github.com/user-attachments/assets/71c1cbd2-e0fa-4b17-96ab-679f32f41603" />



### Evidence — Confidence Scoring, Suspicious Patterns & Watchlist Screening
<img width="1349" height="640" alt="WhatsApp Image 2026-09-05 at 5 16 57 AM" src="https://github.com/user-attachments/assets/c09f121f-1a32-4226-8765-4c3cb3eab50e" />


### STR Report — Auto-Generated Suspicious Transaction Report
<img width="1348" height="638" alt="WhatsApp Image 2026-09-05 at 5 16 58 AM (1)" src="https://github.com/user-attachments/assets/a59d1bdb-ebc5-4632-af64-5cff9a4c15ad" />


### Hardware — Biometric Second-Factor Verification Rig
<img width="727" height="329" alt="hardware-setup" src="https://github.com/user-attachments/assets/ab89f1b5-d544-4690-bce8-a267ee658669" />


---

## Technical Architecture

```
Transaction → Agent 1 (Anomaly Detection) → Adaptive Planner
                                                   │
        ┌──────────────────────────────────────────┼──────────────────────────────┐
        ▼                                           ▼                              ▼
  Agent 2 (Evidence)                    Agent 3 (Network)              Agent 4 (Regulatory)
        └──────────────────────────────────────────┼──────────────────────────────┘
                                                   ▼
                                    Agent 5 (Explanation & STR Draft)
                                                   ▼
                                    Agent 6 (Recommended Action)
                                                   ▼
                                Case Dashboard · Audit Trail · STR Submission
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React, TypeScript, Tailwind CSS, Vite |
| **Backend** | FastAPI, Python, Uvicorn |
| **Database** | MongoDB (async) |
| **Machine Learning** | XGBoost (70%) + Isolation Forest (30%) ensemble, Scikit-learn, SHAP |
| **AI Orchestration** | Custom six-agent pipeline with an Adaptive Planner |
| **Authentication** | JWT + bcrypt, with fingerprint biometric as a second factor |
| **Hardware** | Arduino Uno, fingerprint sensor, buzzer, NeoPixel, 16×2 I²C LCD |
| **Deployment** | Docker, Render (backend), Vercel (frontend), MongoDB Atlas |

**Dataset:** [PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1) — a synthetic mobile-money transaction dataset (6.3M records used for training) with a binary `isFraud` label, a 70/30 stratified train-test split, and 10 engineered features (transaction amount, balance drain, CTR proximity, night activity, risky channel, balance ratio, etc.).

---

## Biometric Security Layer

A physical second factor is required before login completes and before an STR is submitted:

1. Arduino Uno communicates with the backend over USB serial.
2. The fingerprint sensor performs local matching (no raw biometric data leaves the device).
3. The 16×2 I²C LCD shows live verification status (`Finger Required` → `Verifying` → result).
4. A buzzer gives the real-time pass/fail feedback.
5. On success, the backend completes JWT session creation or unlocks STR filing.

---

## Quick Start (Docker — recommended)

```bash
docker-compose up --build

# First time only — seeds users + 500 transactions + fraud cases
docker-compose exec api python seed.py

# Open http://localhost:5173
# Login: admin@finguard.ai / Admin@1234
```

## Manual Setup

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edit MONGODB_URL and SECRET_KEY
python seed.py              # requires MongoDB running
uvicorn app.main:app --reload --port 8000
# Swagger docs → http://localhost:8000/docs
```

### Frontend

```bash
# from project root
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm install && npm run dev
# → http://localhost:5173
```

### Arduino / Biometric Module (optional)

```bash
cd arduino
# Flash the sketch to an Arduino Uno wired to the fingerprint sensor, buzzer, NeoPixel, and 16x2 I2C LCD
# Set the correct serial port in the backend's .env before starting the API
```

### Default Credentials (after `seed.py`)

| Role | Email | Password |
|---|---|---|
| Admin | `admin@finguard.ai` | `Admin@1234` |
| Analyst | `analyst@finguard.ai` | `Analyst@1234` |

> Change these before any production or public deployment.

---

## Project Structure

```
FinGuard-AI/
├── arduino/                  Fingerprint / biometric second-factor sketch
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app + lifespan
│   │   ├── core/              Config, JWT/bcrypt security, audit logging
│   │   ├── db/                 Async MongoDB session + repositories
│   │   ├── api/routes/        auth, transactions, cases, predictions, analytics
│   │   ├── services/           fraud_prediction.py (ML), case_service.py
│   │   └── workers/           Background transaction-processing worker
│   ├── seed.py                Seeds users, transactions, and fraud cases
│   └── requirements.txt
├── src/app/                  React + TypeScript frontend (Vite)
│   ├── services/api.ts        Normalises API responses (camelCase + Date objects)
│   ├── hooks/useApi.ts
│   ├── pages/                 Dashboard, CaseDetail, Analytics, LoginPage
│   └── components/
│       ├── dashboard/CaseQueue.tsx
│       └── case/               TransactionTimeline, EvidencePanel, NetworkGraph, STRReport
├── guidelines/                Project/design guidelines
├── docker-compose.yml
├── render.yaml
└── vercel.json
```

---

## Results

- XGBoost and Isolation Forest models trained and successfully loaded by the application.
- End-to-end biometric login flow demonstrated: password → biometric challenge → fingerprint verification → JWT session.
- Six-agent investigation pipeline executed successfully on seeded transactions, with the Adaptive Planner correctly skipping network analysis for low-risk transactions.
- Example high-risk case: **8 connected nodes**, **4 auto-created sub-cases**, multiple FATF typologies identified, with recommended actions of `BLOCK` and `FILE_STR`.

---

## Feasibility & Impact

**Operational impact:** faster AML investigations, more consistent regulatory assessment, better evidence visibility for compliance officers, and improved security for high-risk regulatory actions.

**Technical feasibility:** built entirely on established open-source technologies, a modular architecture that supports independent testing/extension, a Dockerized deployment, and an ML pipeline that runs without any paid third-party AI APIs.

---

## Future Enhancements

- **Inter-Bank Fraud Intelligence Network** — shares anonymized fraud fingerprints and risk indicators across banks while preserving customer privacy.
- **Fraud Intelligence Marketplace** — lets banks securely share and exchange verified fraud intelligence.
- **Behavioral Fraud Fingerprinting (Fraud DNA)** — builds unique behavioural profiles to catch recurring fraud patterns.
- **AI Case Merger** — automatically detects and merges related investigations to cut duplicate work.
- **Regulatory Compliance Score** — AI checks whether an investigation is legally complete before an STR is filed.

---

## Hackathon

Built for **Smart Horizon 2026 — 48-Hour International Hackathon**
---

## License & Attributions

See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for third-party libraries, datasets, and credits.
