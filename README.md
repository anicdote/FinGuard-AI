# FinGuard AI

### AI-Assisted Financial Crime Detection & Investigation Platform

FinGuard AI is a full-stack platform for detecting suspicious financial activity and supporting compliance investigations using **behavioral machine learning, multi-agent investigation, transaction-network analysis, and human-in-the-loop decision support**.

FinGuard AI provides investigation and decision support. Final compliance decisions remain with authorized human investigators.

---

## ✨ Features

* **Behavioral Fraud Detection** using XGBoost + Isolation Forest
* **Adaptive Multi-Agent Investigation** with six specialized agents
* **Evidence Gathering** including transaction patterns, watchlist and PEP signals
* **Transaction Network Analysis** for connected-account investigation
* **Regulatory Assessment & STR Drafting**
* **AI-Assisted Decision Synthesis** with actionable recommendations
* **Case Management** with role-based access
* **Human Review & Recommendation Override**
* **False-Positive Feedback**
* **Audit Trail** for investigation actions
* **Analytics Dashboard**
* **Fingerprint Authentication**

---

## 🧠 Investigation Pipeline

```text
Transaction
     ↓
Behavioral ML Detection
     ↓
Adaptive Investigation Planner
     ↓
┌─────────────────────────────────┐
│ Agent 1 — Anomaly Detection     │
│ Agent 2 — Evidence Gathering    │
│ Agent 3 — Network Investigation │
│ Agent 4 — Regulatory Assessment │
│ Agent 5 — Explanation / STR     │
│ Agent 6 — Decision Synthesis    │
└─────────────────────────────────┘
     ↓
Investigation Case
     ↓
Human Investigator Review
     ↓
Final Action
```

The planner can conditionally route investigations based on the available evidence instead of executing every investigation stage for every transaction.

---

## 🤖 Machine Learning

FinGuard AI currently uses an ensemble of:

* **XGBoost** for behavioral classification
* **Isolation Forest** for anomaly detection

The model incorporates transaction and behavioral features such as:

* Transaction amount and type
* Transaction frequency
* Time-of-day behavior
* Historical transaction patterns
* Amount-to-history ratios
* Time since previous activity

---

## 🛠️ Tech Stack

**Frontend**

React · TypeScript · Vite · Material UI · Tailwind CSS · Recharts

**Backend**

Python · FastAPI · Uvicorn · Pydantic · JWT · bcrypt

**Data & ML**

MongoDB  · XGBoost · scikit-learn · Joblib · NumPy

**Hardware**

Arduino Uno ·  Fingerprint Sensor · Serial Communication

---

## 📁 Project Structure

```text
FinGuard-AI/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── db/
│   │   ├── services/
│   │   └── workers/
│   ├── models/
│   ├── seed.py
│   └── requirements.txt
│
├── src/
│   └── app/
│       ├── components/
│       ├── context/
│       ├── hooks/
│       ├── pages/
│       └── services/
│
├── arduino/
│   └── finguard_biometric.ino
│
├── docker-compose.yml
├── render.yaml
├── vercel.json
└── README.md
```

---

## 🚀 Getting Started

### Docker — Recommended

Make sure Docker is installed, then run:

```bash
docker-compose up --build
```

The application will be available at:

```text
Frontend → http://localhost:5173
Backend  → http://localhost:8000
API Docs → http://localhost:8000/docs
```

### Seed Demo Data

```bash
docker-compose exec api python seed.py
```

This creates demo users and sample transactions for local testing.

---

## ⚙️ Manual Setup

### Backend

```bash
cd backend

python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` from `.env.example`, configure MongoDB and `SECRET_KEY`, then run:

```bash
uvicorn app.main:app --reload --port 8000
```

### Frontend

From the project root:

```bash
npm install
```

Create `.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

Run:

```bash
npm run dev
```

---

## 🔐 Security & Access Control

FinGuard AI includes:

* JWT authentication
* Password hashing
* Role-based authorization
* Role-aware case access
* Protected investigator actions
* Case audit logging
* Administrator-controlled biometric enrollment

Supported application roles include **Admin, Manager, Officer, and Analyst**.

---

## 📊 Case Decisions

The decision-support layer can produce operational recommendations such as:

```text
BLOCK
MONITOR
ESCALATE
FILE_STR
REQUEST_INFO
CLOSE
```

These recommendations combine investigation evidence and risk signals. They are intended to support investigators and **do not constitute autonomous legal or regulatory decisions**.

##
