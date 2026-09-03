import { Case, Transaction } from './transactions';
import { generateSuspiciousTransactions, allTransactions } from './transactions';
import { runMultiAgentPipeline } from './agents';

// ── Hardcoded case scenarios so we always get 6 rich cases ──────────
function buildCase2(): Transaction[] {
  // Case 2: Night-time velocity burst — 8 rapid IMPS transfers at 1AM
  const base = new Date(); base.setDate(base.getDate() - 1); base.setHours(1, 0);
  return Array.from({ length: 8 }, (_, i) => {
    const t = new Date(base); t.setMinutes(i * 7);
    return {
      id: `TXN2${i.toString().padStart(3,'0')}`,
      accountId: 'ACC87654321',
      accountName: 'Priya Sharma',
      amount: 920000 + i * 15000,
      currency: 'INR',
      timestamp: t,
      type: 'debit' as const,
      counterparty: 'Swift Cash Services',
      counterpartyAccount: `DEST${i}ACC`,
      location: i % 2 === 0 ? 'Singapore' : 'Mumbai',
      channel: 'IMPS',
      description: 'Urgent transfer',
      paySimType: 'TRANSFER' as const,
      oldbalanceOrg: 8000000 - i * 920000,
      newbalanceOrig: 8000000 - (i + 1) * 920000,
      oldbalanceDest: 0,
      newbalanceDest: 920000 + i * 15000,
      isFraud: true,
    };
  });
}

function buildCase3(): Transaction[] {
  // Case 3: Trade-based money laundering — large RTGS to high-risk counterparty
  const base = new Date(); base.setDate(base.getDate() - 5);
  const amounts = [4800000, 3200000, 5100000, 2900000, 4500000];
  return amounts.map((amount, i) => {
    const t = new Date(base); t.setDate(t.getDate() + i);
    return {
      id: `TXN3${i.toString().padStart(3,'0')}`,
      accountId: 'ACC11223344',
      accountName: 'Mohammed Yusuf',
      amount,
      currency: 'INR',
      timestamp: t,
      type: 'debit' as const,
      counterparty: 'Indo-Gulf Trading Co',
      counterpartyAccount: `GULF${i}ACC`,
      location: 'Dubai',
      channel: 'Wire Transfer',
      description: 'Trade settlement',
      paySimType: 'TRANSFER' as const,
      oldbalanceOrg: 25000000 - i * amount,
      newbalanceOrig: 25000000 - (i + 1) * amount,
      oldbalanceDest: 1000000,
      newbalanceDest: 1000000 + amount,
      isFraud: true,
    };
  });
}

function buildCase4(): Transaction[] {
  // Case 4: Mule network — small amounts from many sources to one account
  const base = new Date(); base.setDate(base.getDate() - 2);
  return Array.from({ length: 12 }, (_, i) => {
    const t = new Date(base); t.setHours(t.getHours() + i * 2);
    return {
      id: `TXN4${i.toString().padStart(3,'0')}`,
      accountId: `MULE${i}ACC`,
      accountName: ['Arjun Singh', 'Kavitha Iyer', 'Vikram Mehta', 'Sunita Joshi'][i % 4],
      amount: 85000 + i * 5000,
      currency: 'INR',
      timestamp: t,
      type: 'debit' as const,
      counterparty: 'Apex Business Solutions',
      counterpartyAccount: 'ACC99887766',
      location: ['Chennai', 'Hyderabad', 'Kolkata', 'Pune'][i % 4],
      channel: 'UPI',
      description: 'Payment',
      paySimType: 'PAYMENT' as const,
      oldbalanceOrg: 200000,
      newbalanceOrig: 200000 - (85000 + i * 5000),
      oldbalanceDest: i * 90000,
      newbalanceDest: i * 90000 + 85000 + i * 5000,
      isFraud: true,
    };
  });
}

function buildCase5(): Transaction[] {
  // Case 5: Cash-intensive ATM withdrawals — multiple ATM hits across cities
  const base = new Date(); base.setDate(base.getDate() - 4);
  const cities = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune'];
  return Array.from({ length: 6 }, (_, i) => {
    const t = new Date(base); t.setDate(t.getDate() + i); t.setHours(23, 30);
    return {
      id: `TXN5${i.toString().padStart(3,'0')}`,
      accountId: 'ACC55443322',
      accountName: 'Suresh Nair',
      amount: 200000,
      currency: 'INR',
      timestamp: t,
      type: 'debit' as const,
      counterparty: 'ATM Withdrawal',
      counterpartyAccount: 'CASH',
      location: cities[i],
      channel: 'ATM',
      description: 'Cash withdrawal',
      paySimType: 'CASH_OUT' as const,
      oldbalanceOrg: 1500000 - i * 200000,
      newbalanceOrig: 1500000 - (i + 1) * 200000,
      oldbalanceDest: 0,
      newbalanceDest: 0,
      isFraud: true,
    };
  });
}

function buildCase6(): Transaction[] {
  // Case 6: Crypto gateway layering — rapid deposits then immediate withdrawals
  const base = new Date(); base.setDate(base.getDate() - 7);
  return Array.from({ length: 10 }, (_, i) => {
    const t = new Date(base); t.setHours(t.getHours() + i * 4);
    const isDeposit = i % 2 === 0;
    return {
      id: `TXN6${i.toString().padStart(3,'0')}`,
      accountId: 'ACC66778899',
      accountName: 'Deepika Reddy',
      amount: 750000 + i * 50000,
      currency: 'INR',
      timestamp: t,
      type: isDeposit ? 'credit' as const : 'debit' as const,
      counterparty: isDeposit ? 'National Trade Corp' : 'Crypto Bazaar Ltd',
      counterpartyAccount: `CRYPTO${i}ACC`,
      location: isDeposit ? 'Bangalore' : 'Hong Kong',
      channel: isDeposit ? 'NEFT' : 'Wire Transfer',
      description: isDeposit ? 'Incoming transfer' : 'Crypto purchase',
      paySimType: isDeposit ? 'CASH_IN' as const : 'TRANSFER' as const,
      oldbalanceOrg: 5000000,
      newbalanceOrig: 5000000,
      oldbalanceDest: 100000,
      newbalanceDest: 100000 + 750000 + i * 50000,
      isFraud: true,
    };
  });
}

function generateCases(): Case[] {
  const cases: Case[] = [];

  // Case 1: Structuring + account drain (always generates, highest risk)
  const case1 = runMultiAgentPipeline(generateSuspiciousTransactions(), allTransactions);
  case1.priority = 'critical'; // Force critical — structuring + drain + international = highest severity
  case1.riskScore = Math.max(case1.riskScore, 85);
  cases.push(case1);

  // Cases 2-6: Hardcoded scenarios
  const case2 = runMultiAgentPipeline(buildCase2(), allTransactions);
  case2.priority = 'high';
  case2.riskScore = Math.max(case2.riskScore, 72);
  cases.push(case2);

  cases.push(runMultiAgentPipeline(buildCase3(), allTransactions));
  cases.push(runMultiAgentPipeline(buildCase4(), allTransactions));
  cases.push(runMultiAgentPipeline(buildCase5(), allTransactions));
  cases.push(runMultiAgentPipeline(buildCase6(), allTransactions));

  return cases.sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return order[a.priority] - order[b.priority];
  });
}

export const mockCases = generateCases();

export const dashboardStats = {
  totalCases: mockCases.length,
  criticalCases: mockCases.filter(c => c.priority === 'critical').length,
  highPriorityCases: mockCases.filter(c => c.priority === 'high').length,
  avgProcessingTime: 7.3,
  totalTransactionsAnalyzed: allTransactions.length + 500,
  suspiciousAccountsIdentified: mockCases.length,
  averageRiskScore: mockCases.reduce((sum, c) => sum + c.riskScore, 0) / mockCases.length,
  strFilingsPending: mockCases.filter(c => c.status === 'new').length,
  last24Hours: {
    newCases: 3,
    totalAmount: mockCases.slice(0, 3).reduce(
      (sum, c) => sum + c.suspiciousTransactions.reduce((s, t) => s + t.amount, 0), 0
    ),
  },
};
