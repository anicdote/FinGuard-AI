// PaySim-compatible transaction data for FinGuard AI
// Based on: Lopez-Rojas, E.A., Elmir, A., Axelsson, S. (2016).
// PaySim: A Financial Mobile Money Simulator for Fraud Detection. EMSS 2016.

export interface Transaction {
  id: string;
  accountId: string;
  accountName: string;
  amount: number;
  currency: string;
  timestamp: Date;
  type: 'credit' | 'debit';
  counterparty: string;
  counterpartyAccount: string;
  location: string;
  channel: string;
  description: string;
  // PaySim fields
  paySimType: 'PAYMENT' | 'TRANSFER' | 'CASH_OUT' | 'CASH_IN' | 'DEBIT';
  oldbalanceOrg: number;
  newbalanceOrig: number;
  oldbalanceDest: number;
  newbalanceDest: number;
  isFraud: boolean;
}

export interface Case {
  id: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'new' | 'investigating' | 'reviewed' | 'filed';
  accountId: string;
  accountName: string;
  detectedAt: Date;
  anomalyScore: number;
  riskScore: number;
  fatfTypology: string[];
  transactionIds: string[];
  suspiciousTransactions: Transaction[];
  evidenceSummary: {
    velocityScore: number;
    structuringScore: number;
    networkScore: number;
    unusualPatterns: string[];
  };
  strNarrative: string;
  networkAnalysis: {
    connectedAccounts: string[];
    suspiciousLinks: Array<{ from: string; to: string; weight: number }>;
    pageRankScore: number;
    componentSize: number;
  };
}

// Indian banking context
const accountNames = [
  'Rajesh Kumar', 'Priya Sharma', 'Mohammed Yusuf', 'Anita Patel',
  'Suresh Nair', 'Deepika Reddy', 'Arjun Singh', 'Kavitha Iyer',
  'Vikram Mehta', 'Sunita Joshi', 'Arun Krishnan', 'Meera Bhat'
];

const companies = [
  'Reliance Trading Pvt Ltd', 'Global Exports Corp', 'Mumbai Finance House',
  'Digital Pay Solutions', 'Quick Transfer Services', 'Sunrise Enterprises',
  'Crypto Bazaar Ltd', 'Indo-Gulf Trading Co', 'Swift Cash Services',
  'Apex Business Solutions', 'National Trade Corp', 'PayEase India'
];

// Indian cities + high-risk international jurisdictions (FATF flagged)
const locations = [
  'Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad',
  'Dubai', 'Singapore', 'Hong Kong', 'Kolkata', 'Pune'
];

const channels = ['UPI', 'NEFT', 'RTGS', 'IMPS', 'Branch', 'ATM', 'Wire Transfer', 'Mobile Banking'];

function generateTxnId(): string {
  return `TXN${Math.random().toString(36).substr(2, 9).toUpperCase()}`;
}

function generateAccId(): string {
  return `ACC${Math.random().toString(36).substr(2, 8).toUpperCase()}`;
}

// PaySim-style: generate suspicious transactions (structuring + velocity + drain)
export function generateSuspiciousTransactions(): Transaction[] {
  const transactions: Transaction[] = [];
  const suspiciousAccount = 'ACC12345678';
  const suspiciousName = 'Rajesh Kumar';
  const baseTime = new Date();
  baseTime.setDate(baseTime.getDate() - 3);

  // Pattern 1: Structuring — multiple txns just below ₹10L PMLA CTR threshold
  for (let i = 0; i < 7; i++) {
    const time = new Date(baseTime);
    time.setHours(time.getHours() + i * 3);
    const oldBal = 1200000 - i * 95000;
    const amount = 850000 + Math.random() * 140000; // ₹8.5L–₹9.9L (just below ₹10L)
    transactions.push({
      id: generateTxnId(),
      accountId: suspiciousAccount,
      accountName: suspiciousName,
      amount: Math.round(amount),
      currency: 'INR',
      timestamp: time,
      type: 'debit',
      counterparty: companies[Math.floor(Math.random() * companies.length)],
      counterpartyAccount: generateAccId(),
      location: 'Mumbai',
      channel: 'NEFT',
      description: 'Business payment',
      paySimType: 'TRANSFER',
      oldbalanceOrg: oldBal,
      newbalanceOrig: Math.max(0, oldBal - amount),
      oldbalanceDest: 50000,
      newbalanceDest: 50000 + amount,
      isFraud: true,
    });
  }

  // Pattern 2: Account drain — large CASH_OUT draining balance to zero
  const drainTime = new Date(baseTime);
  drainTime.setDate(drainTime.getDate() + 1);
  drainTime.setHours(2, 30); // 2:30 AM — suspicious hour
  transactions.push({
    id: generateTxnId(),
    accountId: suspiciousAccount,
    accountName: suspiciousName,
    amount: 2350000,
    currency: 'INR',
    timestamp: drainTime,
    type: 'debit',
    counterparty: 'Crypto Bazaar Ltd',
    counterpartyAccount: generateAccId(),
    location: 'Dubai',
    channel: 'Wire Transfer',
    description: 'Urgent wire transfer',
    paySimType: 'CASH_OUT',
    oldbalanceOrg: 2350000,
    newbalanceOrig: 0, // Fully drained
    oldbalanceDest: 0,
    newbalanceDest: 2350000,
    isFraud: true,
  });

  // Pattern 3: Rapid velocity — 5 transactions in 1 hour
  const velocityBase = new Date(baseTime);
  velocityBase.setDate(velocityBase.getDate() + 2);
  velocityBase.setHours(22, 0);
  for (let i = 0; i < 5; i++) {
    const time = new Date(velocityBase);
    time.setMinutes(time.getMinutes() + i * 10);
    transactions.push({
      id: generateTxnId(),
      accountId: suspiciousAccount,
      accountName: suspiciousName,
      amount: 75000 + Math.round(Math.random() * 25000),
      currency: 'INR',
      timestamp: time,
      type: 'debit',
      counterparty: companies[i % companies.length],
      counterpartyAccount: generateAccId(),
      location: i % 2 === 0 ? 'Singapore' : 'Mumbai',
      channel: 'IMPS',
      description: 'Payment transfer',
      paySimType: 'PAYMENT',
      oldbalanceOrg: 500000 - i * 80000,
      newbalanceOrig: 500000 - (i + 1) * 80000,
      oldbalanceDest: 10000,
      newbalanceDest: 90000,
      isFraud: true,
    });
  }

  return transactions;
}

// Generate a large pool of normal PaySim-style transactions
function generateNormalTransactions(count: number): Transaction[] {
  const transactions: Transaction[] = [];
  const paySimTypes: Transaction['paySimType'][] = ['PAYMENT', 'TRANSFER', 'CASH_OUT', 'CASH_IN', 'DEBIT'];
  const typeWeights = [35, 20, 20, 15, 10];

  for (let i = 0; i < count; i++) {
    const rand = Math.random() * 100;
    let cumulative = 0;
    let paySimType: Transaction['paySimType'] = 'PAYMENT';
    for (let j = 0; j < typeWeights.length; j++) {
      cumulative += typeWeights[j];
      if (rand < cumulative) { paySimType = paySimTypes[j]; break; }
    }

    const time = new Date();
    time.setDate(time.getDate() - Math.floor(Math.random() * 30));
    time.setHours(Math.floor(Math.random() * 24));

    // Log-normal distribution for realistic Indian transaction amounts
    const logNormal = Math.exp(9.5 + Math.random() * 1.2 - 0.6);
    const amount = Math.min(Math.round(logNormal), 500000);

    const oldBal = Math.round(Math.random() * 200000 + 5000);

    transactions.push({
      id: generateTxnId(),
      accountId: generateAccId(),
      accountName: accountNames[Math.floor(Math.random() * accountNames.length)],
      amount,
      currency: 'INR',
      timestamp: time,
      type: paySimType === 'CASH_IN' ? 'credit' : 'debit',
      counterparty: companies[Math.floor(Math.random() * companies.length)],
      counterpartyAccount: generateAccId(),
      location: locations[Math.floor(Math.random() * locations.length)],
      channel: channels[Math.floor(Math.random() * channels.length)],
      description: 'Regular transaction',
      paySimType,
      oldbalanceOrg: oldBal,
      newbalanceOrig: Math.max(0, oldBal - amount),
      oldbalanceDest: Math.round(Math.random() * 50000),
      newbalanceDest: Math.round(Math.random() * 50000) + amount,
      isFraud: false,
    });
  }

  return transactions;
}

// Export transaction pool (PaySim: 5000+ transactions)
export const allTransactions = generateNormalTransactions(500);
