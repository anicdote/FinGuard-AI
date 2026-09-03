"""
Seed script — populates MongoDB with:
  • 1 default admin + 1 analyst user
  • 500 sample transactions (450 normal + 50 suspicious)
  • Runs the fraud scorer and auto-creates 3 fraud investigation cases

Run once:  python seed.py
"""

import asyncio, sys, os, random, math, uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import init_db, get_db
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.transaction_repo import TransactionRepository
from app.core.security import hash_password

# ── Sample data ────────────────────────────────────────────────────────────────
ACCOUNT_NAMES = [
    "Rajesh Kumar", "Priya Sharma", "Mohammed Yusuf", "Anita Patel",
    "Suresh Nair", "Deepika Reddy", "Arjun Singh", "Kavitha Iyer",
]
COMPANIES = [
    "Reliance Trading Pvt Ltd", "Global Exports Corp", "Mumbai Finance House",
    "Digital Pay Solutions", "Crypto Bazaar Ltd", "Indo-Gulf Trading Co",
]
LOCATIONS    = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Dubai", "Singapore", "Hong Kong"]
CHANNELS     = ["UPI", "NEFT", "RTGS", "IMPS", "Branch", "Wire Transfer", "ATM"]
PAYSIM_TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"]

def make_account_id():
    return "ACC" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))

def random_txn(account_id: str, account_name: str, is_fraud: bool = False) -> dict:
    base  = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
    hour  = random.randint(0, 5) if is_fraud else random.randint(7, 22)
    ts    = base.replace(hour=hour, minute=random.randint(0, 59))
    paysim = random.choice(["CASH_OUT", "TRANSFER"]) if is_fraud else random.choice(PAYSIM_TYPES)
    amount = round(random.uniform(850_000, 980_000), 0) if is_fraud else round(
        math.exp(9.5 + random.gauss(0, 0.6)), 0
    )
    old_bal = round(random.uniform(1_000_000, 5_000_000))
    new_bal = 0 if (is_fraud and random.random() > 0.5) else max(0, old_bal - amount)

    return {
        "id":                 "TXN" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=9)),
        "account_id":         account_id,
        "accountName":        account_name,
        "amount":             abs(amount),
        "currency":           "INR",
        "timestamp":          ts,
        "hour":               hour,
        "type":               "credit" if paysim == "CASH_IN" else "debit",
        "counterparty":       random.choice(COMPANIES),
        "counterpartyAccount": make_account_id(),
        "location":           random.choice(["Dubai", "Singapore", "Hong Kong"]) if is_fraud
                              else random.choice(LOCATIONS),
        "channel":            "Wire Transfer" if is_fraud else random.choice(CHANNELS),
        "description":        "Suspicious transfer" if is_fraud else "Regular transaction",
        "paySimType":         paysim,
        "oldbalanceOrg":      old_bal,
        "newbalanceOrig":     int(new_bal),
        "oldbalanceDest":     round(random.uniform(0, 100_000)),
        "newbalanceDest":     round(random.uniform(0, 100_000)) + abs(amount),
        "analyzed":           False,
    }


async def seed():
    await init_db()
    db = await get_db()

    # ── Users ──────────────────────────────────────────────────────────────────
    user_repo = UserRepository(db)
    if not await user_repo.get_by_email("admin@finguard.ai"):
        await user_repo.create({
            "email": "admin@finguard.ai",
            "hashed_password": hash_password("Admin@1234"),
            "name": "System Admin", "role": "admin",
        })
        print("✓ Admin user  →  admin@finguard.ai / Admin@1234")
    else:
        print("  Admin user already exists")

    if not await user_repo.get_by_email("analyst@finguard.ai"):
        await user_repo.create({
            "email": "analyst@finguard.ai",
            "hashed_password": hash_password("Analyst@1234"),
            "name": "FIU Analyst", "role": "analyst",
        })
        print("✓ Analyst user  →  analyst@finguard.ai / Analyst@1234")
    else:
        print("  Analyst user already exists")

    # Phase 8 — role-based visibility needs at least one manager account to
    # demo case assignment. Additive only; doesn't touch the admin/analyst seeds above.
    if not await user_repo.get_by_email("manager@finguard.ai"):
        await user_repo.create({
            "email": "manager@finguard.ai",
            "hashed_password": hash_password("Manager@1234"),
            "name": "Compliance Manager", "role": "manager",
        })
        print("✓ Manager user →  manager@finguard.ai / Manager@1234")
    else:
        print("  Manager user already exists")

    # ── Reset demo transactions/cases ───────────────────────────────────────
    # IMPORTANT: seed only creates fresh, UNANALYZED transactions.
    # The background worker is the sole path that runs the Adaptive Planner,
    # creates cases, and persists Agent 1–6 investigation results.
    await db.cases.delete_many({})
    await db.transactions.delete_many({})
    print("  Cleared existing demo transactions and cases")

    accounts = [(make_account_id(), random.choice(ACCOUNT_NAMES)) for _ in range(12)]
    fraud_accounts = accounts[:3]
    txns = []

    for _ in range(450):
        acc_id, acc_name = random.choice(accounts)
        txns.append(random_txn(acc_id, acc_name, is_fraud=False))

    for i in range(50):
        acc_id, acc_name = fraud_accounts[i % 3]
        txns.append(random_txn(acc_id, acc_name, is_fraud=True))

    random.shuffle(txns)
    await db.transactions.insert_many(txns)
    print(f"✓ Seeded {len(txns)} transactions (450 normal + 50 suspicious)")
    print("  All transactions remain analyzed=False so the Adaptive Planner processes them.")

    print("\n✅ Seed complete. Start the server: uvicorn app.main:app --reload")


def _build_case(account_id: str, txns: list) -> dict:
    amounts    = [t.get("amount", 0) for t in txns]
    risk_score = min(100.0, sum(t.get("fraud_probability", 0.5) * 100 for t in txns) / len(txns))
    fatf       = _detect_typologies(txns)
    evidence   = _evidence_summary(txns)
    network    = _network_analysis(account_id, txns)
    total_amt  = sum(amounts)
    name       = txns[0].get("accountName", "Unknown")

    return {
        "id":              str(uuid.uuid4()),
        "account_id":      account_id,
        "accountName":     name,
        "status":          "new",
        "priority":        _priority(risk_score),
        "risk_score":      round(risk_score, 2),
        "anomaly_score":   round(risk_score / 100, 3),
        "fatf_typology":   fatf,
        "transaction_ids": [t.get("_id", t.get("id")) for t in txns],
        "suspicious_transactions": txns,
        "total_amount":    total_amt,
        "evidence_summary": evidence,
        "str_narrative":   _narrative(account_id, txns, fatf),
        "network_analysis": network,
        "detected_at":     datetime.now(timezone.utc).isoformat(),
    }

def _priority(score: float) -> str:
    if score >= 85: return "critical"
    if score >= 65: return "high"
    if score >= 40: return "medium"
    return "low"

def _detect_typologies(txns: list) -> list:
    types = []
    amounts = [t.get("amount", 0) for t in txns]
    if sum(1 for a in amounts if 850_000 <= a < 1_000_000) >= 3:
        types.append("Structuring / Smurfing")
    if any(t.get("location") in {"Dubai", "Hong Kong", "Singapore"} for t in txns):
        types.append("Cross-border Layering")
    if any(t.get("newbalanceOrig") == 0 for t in txns):
        types.append("Account Drain")
    if any(t.get("channel") == "Wire Transfer" for t in txns):
        types.append("Trade-Based Money Laundering")
    return types or ["Suspicious Activity"]

def _evidence_summary(txns: list) -> dict:
    structuring = sum(1 for t in txns if 850_000 <= t.get("amount", 0) < 1_000_000)
    intl        = sum(1 for t in txns if t.get("location") in {"Dubai", "Hong Kong", "Singapore"})
    patterns    = []
    if structuring >= 3:
        patterns.append(f"{structuring} transactions just below ₹10L PMLA CTR threshold")
    if intl >= 2:
        patterns.append(f"{intl} cross-border transactions to high-risk jurisdictions")
    night = sum(1 for t in txns if t.get("hour", 12) in range(0, 6))
    if night:
        patterns.append(f"{night} transactions during 00:00–06:00 (suspicious hours)")
    return {
        "velocity_score":    min(len(txns) / 10, 1.0),
        "structuring_score": min(structuring / 5, 1.0),
        "network_score":     min(intl / 4, 1.0),
        "unusual_patterns":  patterns,
    }

def _network_analysis(account_id: str, txns: list) -> dict:
    cps = list({t.get("counterpartyAccount", "") for t in txns if t.get("counterpartyAccount")})
    links = [{"from": account_id, "to": cp, "weight": round(0.3 + 0.1*i, 2)} for i, cp in enumerate(cps[:8])]
    return {
        "connected_accounts": cps[:10],
        "suspicious_links":   links,
        "page_rank_score":    round(0.6 + len(cps) * 0.02, 3),
        "component_size":     len(cps) + 1,
    }

def _narrative(account_id: str, txns: list, typologies: list) -> str:
    total = sum(t.get("amount", 0) for t in txns)
    name  = txns[0].get("accountName", "the subject")
    types = ", ".join(typologies)
    return (
        f"This Suspicious Transaction Report (STR) is filed pursuant to Section 12 of the "
        f"Prevention of Money Laundering Act, 2002 (PMLA). Account holder {name} "
        f"(Account ID: {account_id}) has been identified as engaging in suspicious financial "
        f"activity consistent with {types}. A total of {len(txns)} transactions amounting to "
        f"₹{total:,.0f} were flagged by the FinGuard AI multi-agent detection pipeline."
    )


if __name__ == "__main__":
    asyncio.run(seed())
