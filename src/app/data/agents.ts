// Multi-agent financial crime detection system
import { Transaction, Case } from './transactions';

// Agent 1: Anomaly Detection using Isolation Forest simulation
export class AnomalyDetectionAgent {
  detect(transactions: Transaction[]): Map<string, number> {
    const accountScores = new Map<string, number>();
    
    // Group transactions by account
    const accountTransactions = new Map<string, Transaction[]>();
    transactions.forEach(tx => {
      if (!accountTransactions.has(tx.accountId)) {
        accountTransactions.set(tx.accountId, []);
      }
      accountTransactions.get(tx.accountId)!.push(tx);
    });
    
    // Calculate anomaly score for each account
    accountTransactions.forEach((txs, accountId) => {
      let score = 0;
      
      // Feature 1: Transaction amount variance
      const amounts = txs.map(t => t.amount);
      const avgAmount = amounts.reduce((a, b) => a + b, 0) / amounts.length;
      const variance = amounts.reduce((sum, amt) => sum + Math.pow(amt - avgAmount, 2), 0) / amounts.length;
      if (variance > 1000000000) score += 0.25; // High variance
      
      // Feature 2: Transaction velocity (transactions per hour)
      const timeSpan = Math.max(...txs.map(t => t.timestamp.getTime())) - 
                       Math.min(...txs.map(t => t.timestamp.getTime()));
      const velocity = (txs.length / (timeSpan / 3600000)); // txs per hour
      if (velocity > 3) score += 0.3;
      
      // Feature 3: Large single transactions
      const largeTransactions = txs.filter(t => t.amount > 100000);
      if (largeTransactions.length > 0) score += 0.2;
      
      // Feature 4: International transactions
      const intlTransactions = txs.filter(t => 
        ['Dubai', 'Singapore', 'Hong Kong', 'London', 'New York'].includes(t.location)
      );
      if (intlTransactions.length > 2) score += 0.25;
      
      accountScores.set(accountId, Math.min(score, 1));
    });
    
    return accountScores;
  }
}

// Agent 2: Evidence Gathering (Velocity & Structuring Detection)
export class EvidenceGatheringAgent {
  analyze(transactions: Transaction[]) {
    const evidence = {
      velocityScore: this.calculateVelocityScore(transactions),
      structuringScore: this.detectStructuring(transactions),
      unusualPatterns: [] as string[]
    };
    
    // Detect patterns
    const timeSpan = (Math.max(...transactions.map(t => t.timestamp.getTime())) - 
                      Math.min(...transactions.map(t => t.timestamp.getTime()))) / 3600000;
    const txPerHour = transactions.length / Math.max(timeSpan, 1);
    
    if (txPerHour > 5) {
      evidence.unusualPatterns.push(`Extremely high velocity: ${txPerHour.toFixed(1)} transactions/hour`);
    }
    
    const justBelowThreshold = transactions.filter(t => t.amount >= 45000 && t.amount < 50000);
    if (justBelowThreshold.length > 2) {
      evidence.unusualPatterns.push(`${justBelowThreshold.length} transactions just below ₹10 lakh PMLA CTR threshold (structuring)`);
    }
    
    const roundAmounts = transactions.filter(t => t.amount % 10000 === 0);
    if (roundAmounts.length > transactions.length * 0.5) {
      evidence.unusualPatterns.push('High frequency of round number transactions (potential layering)');
    }
    
    const nightTransactions = transactions.filter(t => {
      const hour = t.timestamp.getHours();
      return hour >= 23 || hour <= 5;
    });
    if (nightTransactions.length > 5) {
      evidence.unusualPatterns.push(`${nightTransactions.length} transactions during suspicious hours (11 PM - 5 AM)`);
    }
    
    return evidence;
  }
  
  private calculateVelocityScore(transactions: Transaction[]): number {
    if (transactions.length === 0) return 0;
    
    const timeSpan = (Math.max(...transactions.map(t => t.timestamp.getTime())) - 
                      Math.min(...transactions.map(t => t.timestamp.getTime()))) / 3600000;
    const velocity = transactions.length / Math.max(timeSpan, 1);
    
    // Score from 0-100
    return Math.min(velocity * 10, 100);
  }
  
  private detectStructuring(transactions: Transaction[]): number {
    const threshold = 1000000; // ₹10 lakh PMLA CTR threshold
    const justBelow = transactions.filter(t => 
      t.amount >= threshold * 0.9 && t.amount < threshold
    );
    
    // Score from 0-100
    return Math.min((justBelow.length / transactions.length) * 200, 100);
  }
}

// Agent 3: Regulatory Risk Scoring (FATF Typologies)
export class RegulatoryRiskAgent {
  assessRisk(transactions: Transaction[], evidence: any): {
    score: number;
    typologies: string[];
    pmlaConcerns: string[];
  } {
    const typologies: string[] = [];
    const pmlaConcerns: string[] = [];
    let riskScore = 0;
    
    // FATF Typology 1: Structuring / Smurfing
    if (evidence.structuringScore > 50) {
      typologies.push('FATF-T1: Structuring/Smurfing');
      pmlaConcerns.push('Section 12(1)(a) PMLA 2002: Suspicious structuring pattern');
      riskScore += 25;
    }
    
    // FATF Typology 2: Trade-Based Money Laundering
    const largeTradeTxs = transactions.filter(t => 
      t.amount > 500000 && 
      (t.counterparty.includes('Trading') || t.counterparty.includes('Corp'))
    );
    if (largeTradeTxs.length > 2) {
      typologies.push('FATF-T2: Trade-Based Money Laundering');
      pmlaConcerns.push('High-value trade transactions require enhanced due diligence');
      riskScore += 20;
    }
    
    // FATF Typology 3: Cash Intensive Business
    const cashChannels = transactions.filter(t => t.channel === 'ATM' || t.channel === 'Branch');
    if (cashChannels.length > transactions.length * 0.6) {
      typologies.push('FATF-T3: Cash-Intensive Business Model');
      pmlaConcerns.push('Unusual cash activity pattern detected');
      riskScore += 15;
    }
    
    // International Wire Transfers (FIU-IND high-risk indicator)
    const intlWires = transactions.filter(t => 
      t.channel === 'Wire Transfer' && 
      !['Mumbai', 'Delhi', 'Bangalore'].includes(t.location)
    );
    if (intlWires.length > 0) {
      typologies.push('FATF-T4: Cross-Border Wire Transfers');
      pmlaConcerns.push('FIU-IND Alert: Multiple international wire transfers to high-risk jurisdictions');
      riskScore += 30;
    }
    
    // Rapid Movement (Layering)
    if (evidence.velocityScore > 70) {
      typologies.push('FATF-T5: Rapid Movement of Funds (Layering)');
      pmlaConcerns.push('Section 3 PMLA 2002: Potential layering activity detected');
      riskScore += 20;
    }
    
    return {
      score: Math.min(riskScore, 100),
      typologies,
      pmlaConcerns
    };
  }
}

// Agent 4: STR Narrative Generation (Mock LLM using Llama 3 style)
export class STRNarrativeAgent {
  generate(accountName: string, transactions: Transaction[], evidence: any, risk: any): string {
    const totalAmount = transactions.reduce((sum, t) => sum + t.amount, 0);
    const avgAmount = totalAmount / transactions.length;
    
    let narrative = `**SUSPICIOUS TRANSACTION REPORT (STR)**\n\n`;
    narrative += `**Filing Entity:** FinGuard AI Compliance System\n`;
    narrative += `**Report Date:** ${new Date().toISOString().split('T')[0]}\n`;
    narrative += `**Regulatory Framework:** PMLA 2002, FIU-IND Guidelines\n\n`;
    
    narrative += `**SUBJECT IDENTIFICATION**\n`;
    narrative += `Account Holder: ${accountName}\n`;
    narrative += `Account ID: ${transactions[0].accountId}\n\n`;
    
    narrative += `**SUSPICIOUS ACTIVITY SUMMARY**\n`;
    narrative += `Our automated surveillance system flagged ${transactions.length} transactions `;
    narrative += `totaling ₹${totalAmount.toLocaleString('en-IN')} executed between `;
    narrative += `${transactions[transactions.length - 1].timestamp.toLocaleDateString()} and `;
    narrative += `${transactions[0].timestamp.toLocaleDateString()}.\n\n`;
    
    narrative += `**RED FLAGS IDENTIFIED**\n`;
    evidence.unusualPatterns.forEach((pattern: string, idx: number) => {
      narrative += `${idx + 1}. ${pattern}\n`;
    });
    narrative += `\n`;
    
    narrative += `**REGULATORY CONCERNS**\n`;
    risk.pmlaConcerns.forEach((concern: string, idx: number) => {
      narrative += `${idx + 1}. ${concern}\n`;
    });
    narrative += `\n`;
    
    narrative += `**FATF TYPOLOGY MAPPING**\n`;
    risk.typologies.forEach((typology: string, idx: number) => {
      narrative += `${idx + 1}. ${typology}\n`;
    });
    narrative += `\n`;
    
    narrative += `**RISK ASSESSMENT**\n`;
    narrative += `Transaction Velocity Score: ${evidence.velocityScore.toFixed(1)}/100\n`;
    narrative += `Structuring Detection Score: ${evidence.structuringScore.toFixed(1)}/100\n`;
    narrative += `Overall Risk Score: ${risk.score}/100\n\n`;
    
    narrative += `**RECOMMENDATION**\n`;
    if (risk.score > 75) {
      narrative += `IMMEDIATE ESCALATION REQUIRED: File STR with FIU-IND within 24 hours. `;
      narrative += `Consider account freeze pending investigation.\n`;
    } else if (risk.score > 50) {
      narrative += `HIGH PRIORITY: File STR with FIU-IND within 7 days. Enhanced monitoring required.\n`;
    } else {
      narrative += `MEDIUM PRIORITY: Continue enhanced monitoring. File STR if pattern persists.\n`;
    }
    
    narrative += `\n**COMPLIANCE OFFICER REVIEW REQUIRED**\n`;
    narrative += `This automated report requires human validation before submission to regulatory authorities.`;
    
    return narrative;
  }
}

// Agent 5: Network Graph Analysis
export class NetworkAnalysisAgent {
  analyze(transactions: Transaction[], allTransactions: Transaction[]) {
    const mainAccountId = transactions[0].accountId;
    
    // Build network graph
    const connectedAccounts = new Set<string>();
    const links: Array<{ from: string; to: string; weight: number }> = [];
    
    // First degree connections
    transactions.forEach(tx => {
      const counterpartyId = tx.counterpartyAccount;
      connectedAccounts.add(counterpartyId);
      
      links.push({
        from: tx.type === 'debit' ? mainAccountId : counterpartyId,
        to: tx.type === 'debit' ? counterpartyId : mainAccountId,
        weight: tx.amount
      });
    });
    
    // Second degree connections (money mule detection)
    allTransactions.forEach(tx => {
      if (connectedAccounts.has(tx.accountId) && tx.accountId !== mainAccountId) {
        const secondDegree = tx.counterpartyAccount;
        
        // Check if second degree also connects back (suspicious loop)
        const hasLoop = allTransactions.some(t => 
          t.accountId === secondDegree && 
          connectedAccounts.has(t.counterpartyAccount)
        );
        
        if (hasLoop) {
          connectedAccounts.add(secondDegree);
          links.push({
            from: tx.accountId,
            to: secondDegree,
            weight: tx.amount
          });
        }
      }
    });
    
    // Calculate PageRank score (simplified)
    const pageRankScore = this.calculatePageRank(mainAccountId, links);
    
    // Detect strongly connected components
    const componentSize = this.detectSCC(mainAccountId, links);
    
    return {
      connectedAccounts: Array.from(connectedAccounts),
      suspiciousLinks: links,
      pageRankScore,
      componentSize
    };
  }
  
  private calculatePageRank(nodeId: string, links: Array<{ from: string; to: string; weight: number }>): number {
    // Simplified PageRank: based on weighted in-degree
    const incomingWeight = links
      .filter(l => l.to === nodeId)
      .reduce((sum, l) => sum + l.weight, 0);
    
    const outgoingWeight = links
      .filter(l => l.from === nodeId)
      .reduce((sum, l) => sum + l.weight, 0);
    
    // Normalize to 0-1 scale
    return Math.min((incomingWeight + outgoingWeight) / 10000000, 1);
  }
  
  private detectSCC(nodeId: string, links: Array<{ from: string; to: string; weight: number }>): number {
    // Count nodes in the same component
    const visited = new Set<string>();
    const queue = [nodeId];
    
    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;
      
      visited.add(current);
      
      // Add all connected nodes
      links.forEach(link => {
        if (link.from === current && !visited.has(link.to)) {
          queue.push(link.to);
        }
        if (link.to === current && !visited.has(link.from)) {
          queue.push(link.from);
        }
      });
    }
    
    return visited.size;
  }
}

// Main orchestration: Run all agents
export function runMultiAgentPipeline(suspiciousTransactions: Transaction[], allTransactions: Transaction[]): Case {
  console.log('[FinGuard AI] Starting multi-agent pipeline...');
  
  const startTime = Date.now();
  
  // Agent 1: Anomaly Detection
  const anomalyAgent = new AnomalyDetectionAgent();
  const anomalyScores = anomalyAgent.detect([...suspiciousTransactions, ...allTransactions.slice(0, 50)]);
  const anomalyScore = anomalyScores.get(suspiciousTransactions[0].accountId) || 0;
  console.log(`[Agent 1] Anomaly Detection: Score ${anomalyScore.toFixed(2)}`);
  
  // Agent 2: Evidence Gathering
  const evidenceAgent = new EvidenceGatheringAgent();
  const evidence = evidenceAgent.analyze(suspiciousTransactions);
  console.log(`[Agent 2] Evidence Gathering: ${evidence.unusualPatterns.length} patterns detected`);
  
  // Agent 3: Regulatory Risk Assessment
  const riskAgent = new RegulatoryRiskAgent();
  const risk = riskAgent.assessRisk(suspiciousTransactions, evidence);
  console.log(`[Agent 3] Risk Assessment: Score ${risk.score}, ${risk.typologies.length} typologies`);
  
  // Agent 4: STR Narrative
  const narrativeAgent = new STRNarrativeAgent();
  const strNarrative = narrativeAgent.generate(
    suspiciousTransactions[0].accountName,
    suspiciousTransactions,
    evidence,
    risk
  );
  console.log(`[Agent 4] STR Narrative: Generated ${strNarrative.length} characters`);
  
  // Agent 5: Network Analysis
  const networkAgent = new NetworkAnalysisAgent();
  const networkAnalysis = networkAgent.analyze(suspiciousTransactions, allTransactions);
  console.log(`[Agent 5] Network Analysis: ${networkAnalysis.connectedAccounts.length} connected accounts`);
  
  const processingTime = Date.now() - startTime;
  console.log(`[FinGuard AI] Pipeline completed in ${processingTime}ms`);
  
  // Determine priority
  let priority: 'critical' | 'high' | 'medium' | 'low';
  if (risk.score >= 80) priority = 'critical';
  else if (risk.score >= 60) priority = 'high';
  else if (risk.score >= 40) priority = 'medium';
  else priority = 'low';
  
  return {
    id: `CASE${Date.now().toString(36).toUpperCase()}`,
    priority,
    status: 'new',
    accountId: suspiciousTransactions[0].accountId,
    accountName: suspiciousTransactions[0].accountName,
    detectedAt: new Date(),
    anomalyScore: anomalyScore * 100,
    riskScore: risk.score,
    fatfTypology: risk.typologies,
    transactionIds: suspiciousTransactions.map(t => t.id),
    suspiciousTransactions,
    evidenceSummary: {
      velocityScore: evidence.velocityScore,
      structuringScore: evidence.structuringScore,
      networkScore: networkAnalysis.pageRankScore * 100,
      unusualPatterns: evidence.unusualPatterns
    },
    strNarrative,
    networkAnalysis
  };
}
