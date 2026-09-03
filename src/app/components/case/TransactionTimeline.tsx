import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { ArrowDownRight, ArrowUpRight, MapPin, CreditCard } from "lucide-react";

// Works whether timestamp is a Date or an ISO string
function safeDate(val: any): Date {
  if (!val) return new Date();
  if (val instanceof Date) return val;
  return new Date(val);
}

interface TransactionTimelineProps {
  transactions: any[];
}

export function TransactionTimeline({ transactions }: TransactionTimelineProps) {
  if (!transactions || transactions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Transaction Timeline</CardTitle>
          <CardDescription>No transactions found for this case</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-400 text-center py-8">No transaction data available.</p>
        </CardContent>
      </Card>
    );
  }

  const sorted = [...transactions].sort(
    (a, b) => safeDate(b.timestamp).getTime() - safeDate(a.timestamp).getTime()
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Transaction Timeline</CardTitle>
        <CardDescription>
          Chronological view of {transactions.length} suspicious transactions
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {sorted.map((tx: any, idx: number) => {
            const ts    = safeDate(tx.timestamp);
            const txType = tx.type ?? "debit";
            const isDebit = txType === "debit";
            const amount = tx.amount ?? 0;
            const currency = tx.currency ?? "INR";
            const location = tx.location ?? "—";
            const channel  = tx.channel  ?? "—";
            const txId     = tx.id ?? tx._id ?? `TXN-${idx}`;
            const highRiskJurisdictions = ["Dubai", "Singapore", "Hong Kong", "London", "New York"];

            return (
              <div
                key={txId}
                className="relative flex items-start gap-4 p-4 bg-white border border-slate-200 rounded-lg hover:shadow-md transition-shadow"
              >
                {idx < sorted.length - 1 && (
                  <div className="absolute left-6 top-16 w-0.5 h-8 bg-slate-200" />
                )}

                <div className={`flex-shrink-0 p-3 rounded-lg ${
                  isDebit ? "bg-red-100 text-red-600" : "bg-green-100 text-green-600"
                }`}>
                  {isDebit
                    ? <ArrowDownRight className="w-5 h-5" />
                    : <ArrowUpRight className="w-5 h-5" />
                  }
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-semibold text-slate-900">{txId}</p>
                      <p className="text-sm text-slate-600">
                        {ts.toLocaleDateString("en-IN")} at {ts.toLocaleTimeString("en-IN")}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`text-xl font-bold ${isDebit ? "text-red-600" : "text-green-600"}`}>
                        {isDebit ? "−" : "+"} {currency} {Number(amount).toLocaleString("en-IN")}
                      </p>
                      <Badge variant="outline" className="mt-1">{txType.toUpperCase()}</Badge>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-slate-500">Counterparty</p>
                      <p className="text-slate-900 font-medium">{tx.counterparty ?? "—"}</p>
                      <p className="text-xs text-slate-500">{tx.counterpartyAccount ?? tx.counterparty_account ?? "—"}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Description</p>
                      <p className="text-slate-900 font-medium">{tx.description ?? "—"}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mt-3 text-xs text-slate-600">
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      <span>{location}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <CreditCard className="w-3 h-3" />
                      <span>{channel}</span>
                    </div>
                  </div>

                  {/* Red flag badges */}
                  {(amount > 100000 || highRiskJurisdictions.includes(location)) && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {amount > 1000000 && (
                        <Badge className="bg-red-100 text-red-800 text-xs">Large Amount</Badge>
                      )}
                      {amount >= 850000 && amount < 1000000 && (
                        <Badge className="bg-orange-100 text-orange-800 text-xs">Near CTR Threshold</Badge>
                      )}
                      {highRiskJurisdictions.includes(location) && (
                        <Badge className="bg-purple-100 text-purple-800 text-xs">High-Risk Jurisdiction</Badge>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary footer */}
        <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-slate-900">
                ₹{transactions.reduce((sum: number, t: any) => sum + (t.amount ?? 0), 0).toLocaleString("en-IN")}
              </p>
              <p className="text-sm text-slate-600">Total Amount</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">
                {transactions.filter((t: any) => (t.type ?? "debit") === "debit").length}
              </p>
              <p className="text-sm text-slate-600">Debits</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">
                {transactions.filter((t: any) => t.type === "credit").length}
              </p>
              <p className="text-sm text-slate-600">Credits</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
