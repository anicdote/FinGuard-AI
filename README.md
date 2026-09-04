# FinGuard AI — Full-Stack Fraud Detection System (v2.1 — Fixed)

> PMLA 2002 / FIU-IND compliant · FastAPI + MongoDB + React + JWT Auth

---

## Bug Fixes in This Version (v2.1)

All of the following were broken in v2.0 and are now fixed:

| # | Bug | Fix |
|---|-----|-----|
| 1 | **"Investigate" showed 0 for everything** | `api.ts` now deep-normalises all API responses: snake_case keys → camelCase AND ISO date strings → Date objects automatically |
| 2 | **CaseDetail crashed on open** | `caseData.detectedAt.toLocaleDateString()` called on a raw string — added `safeDate()` helper that handles both strings and Date objects |
| 3 | **Evidence scores always showed 0** | Backend stores scores as `0.0–1.0` floats; frontend was displaying them as-is. Now multiplied ×100 for display |
| 4 | **TransactionTimeline crashed** | `tx.timestamp.getTime()` called on ISO strings — replaced with `safeDate(tx.timestamp).getTime()` |
| 5 | **FATF typologies / network / evidence missing** | All field access now handles both camelCase (after normalisation) and snake_case fallbacks |
| 6 | **CaseQueue broke on API data** | Removed typed `Case` import; now uses `any[]` with safe fallbacks for all fields |
| 7 | **STRReport had broken JSX** | Full rewrite — safe access for `caseData.id ?? caseData._id`, priority, riskScore |
| 8 | **Analytics page used mock data** | Full rewrite using `useCases`, `useDashboardStats`, `useTrend` hooks with live data |
| 9 | **`/case/:id` returned 404 for UUID case IDs** | `case_repo.get_by_id()` now searches by the UUID `id` field first, then falls back to MongoDB `_id` |
| 10 | **Dashboard stats showed 0** | `analytics.py` now returns `averageRiskScore` and `suspiciousAccountsIdentified` fields |
| 11 | **No cases on fresh install** | `seed.py` now scores all transactions and auto-creates fraud investigation cases |
| 12 | **NetworkGraph crashed on empty data** | Added null guards for all array fields; handles zero connected accounts gracefully |

---

## Quick Start (Docker — recommended)

```bash
docker-compose up --build

# First time only — seeds users + 500 transactions + fraud cases
docker-compose exec api python seed.py

# Open http://localhost:5173
# Login: admin@finguard.ai / Admin@1234
```

---

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

---

## Default Credentials (after seed.py)

| Role    | Email                   | Password     |
|---------|-------------------------|--------------|
| Admin   | admin@finguard.ai       | Admin@1234   |
| Analyst | analyst@finguard.ai     | Analyst@1234 |

> Change these in production.

---

## Project Structure

```
finguard_fixed/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI app + lifespan
│   │   ├── core/
│   │   │   ├── config.py              Env-driven settings
│   │   │   ├── security.py            JWT + bcrypt
│   │   │   └── logging.py             Prediction audit logger
│   │   ├── db/
│   │   │   ├── session.py             Async MongoDB + indexes
│   │   │   └── repositories/
│   │   │       ├── transaction_repo.py
│   │   │       ├── case_repo.py       ← Fixed: UUID id lookup
│   │   │       └── user_repo.py
│   │   ├── api/routes/
│   │   │   ├── auth.py
│   │   │   ├── transactions.py
│   │   │   ├── cases.py
│   │   │   ├── predictions.py
│   │   │   └── analytics.py           ← Fixed: all dashboard fields present
│   │   ├── services/
│   │   │   ├── fraud_prediction.py    ML service
│   │   │   └── case_service.py
│   │   └── workers/
│   │       └── background.py          ← Fixed: account_id handling
│   ├── seed.py                        ← Fixed: creates cases, not just txns
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── src/app/
│   ├── services/
│   │   └── api.ts                     ← Fixed: snake→camel + string→Date normalization
│   ├── hooks/useApi.ts                ← Fixed: safe empty-id guard
│   ├── context/AuthContext.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx              Live API hooks
│   │   ├── CaseDetail.tsx             ← Fixed: all crashes, safe field access
│   │   ├── Analytics.tsx              ← Fixed: live data, no mock imports
│   │   └── LoginPage.tsx
│   └── components/
│       ├── dashboard/CaseQueue.tsx    ← Fixed: any[] type, safe field access
│       └── case/
│           ├── TransactionTimeline.tsx ← Fixed: safe Date handling
│           ├── EvidencePanel.tsx       ← Fixed: 0-1 → 0-100 score display
│           ├── NetworkGraph.tsx        ← Fixed: empty data guards
│           └── STRReport.tsx           ← Fixed: full rewrite, no broken JSX
│
├── docker-compose.yml
├── render.yaml
└── vercel.json
```

---

## Deploy to Production

### Backend → Render.com
1. Push to GitHub → Render detects `render.yaml` automatically  
2. Set `MONGODB_URL` in Render dashboard (MongoDB Atlas free tier)  
3. Set `SECRET_KEY` to a random 32-char string  

### Frontend → Vercel
1. Import repo on Vercel  
2. Add env var: `VITE_API_URL=https://finguard-api.onrender.com`  
3. Deploy  

### MongoDB → Atlas (free M0)
1. Create cluster at mongodb.com/atlas  
2. Get connection string → paste as `MONGODB_URL` on Render  
