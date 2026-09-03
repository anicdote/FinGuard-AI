import { useCases, useDashboardStats, useTrend } from "../hooks/useApi";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";

const NAVY = "#1A3A6B";
const RED = "#C0392B";
const ORANGE = "#D35400";
const GREEN = "#1A7A4A";
const AMBER = "#B7791F";

const pct = (v: number) => (v <= 1 ? v * 100 : v);

function formatTrendDate(value: string) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export function Analytics() {
  const { data: cases, loading: casesLoading } = useCases();
  const { data: stats, loading: statsLoading } = useDashboardStats();
  const { data: trend, loading: trendLoading } = useTrend(30);

  const safeCases = cases ?? [];
  const s = stats ?? {
    avgProcessingTime: 0,
    strFilingsPending: 0,
  };

  const priorityData = [
    { name: "Critical", value: safeCases.filter((c: any) => c.priority === "critical").length, color: RED },
    { name: "High", value: safeCases.filter((c: any) => c.priority === "high").length, color: ORANGE },
    { name: "Medium", value: safeCases.filter((c: any) => c.priority === "medium").length, color: AMBER },
    { name: "Low", value: safeCases.filter((c: any) => c.priority === "low").length, color: GREEN },
  ].filter((d) => d.value > 0);

  const typologyCount: Record<string, number> = {};
  safeCases.forEach((c: any) => {
    const types = c.fatfTypology ?? c.fatf_typology ?? [];
    types.forEach((t: string) => {
      typologyCount[t] = (typologyCount[t] ?? 0) + 1;
    });
  });
  const typologyData = Object.entries(typologyCount)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  const riskDistribution = safeCases.map((c: any, index: number) => {
    const ev = c.evidenceSummary ?? c.evidence_summary ?? {};
    return {
      label: `Case ${index + 1}`,
      account: c.accountName ?? c.account_name ?? `Case ${index + 1}`,
      risk: Number(c.riskScore ?? c.risk_score ?? 0),
      velocity: pct(Number(ev.velocityScore ?? ev.velocity_score ?? 0)),
      structuring: pct(Number(ev.structuringScore ?? ev.structuring_score ?? 0)),
    };
  });

  const trendData = (trend ?? []).map((d: any) => ({
    date: d.date ?? d._id ?? d.Id ?? "",
    count: Number(d.count ?? 0),
    fraud: Number(d.fraudCount ?? d.fraud_count ?? 0),
  }));

  const totalCases = safeCases.length;
  const avgRisk = totalCases > 0
    ? (safeCases.reduce((sum: number, c: any) => sum + Number(c.riskScore ?? c.risk_score ?? 0), 0) / totalCases).toFixed(1)
    : "0.0";
  const uniqueTypes = new Set(
    safeCases.flatMap((c: any) => c.fatfTypology ?? c.fatf_typology ?? [])
  ).size;
  const strsPending = Number(s.strFilingsPending ?? 0);
  const avgProcessing = Number(s.avgProcessingTime ?? 0);

  if (casesLoading || statsLoading) {
    return (
      <div className="container mx-auto px-6 py-16 text-center text-slate-400 text-sm">
        Loading analytics…
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-7">
      <div className="mb-6">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 mb-1">Analytics Dashboard</h1>
            <p className="text-sm text-slate-500">
              Investigation workload, risk patterns and regulatory findings from the current case database.
            </p>
          </div>
          <span className="text-xs text-slate-400">Live case database</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Case Priority Distribution</CardTitle>
            <CardDescription>Current investigation queue by severity</CardDescription>
          </CardHeader>
          <CardContent>
            {priorityData.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-16">No cases yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={priorityData}
                    cx="50%"
                    cy="50%"
                    innerRadius={58}
                    outerRadius={92}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                    labelLine={{ stroke: "#94A3B8" }}
                  >
                    {priorityData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">FATF Typology Frequency</CardTitle>
            <CardDescription>Number of cases mapped to each detected typology</CardDescription>
          </CardHeader>
          <CardContent>
            {typologyData.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-16">No typologies yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={typologyData} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                  <YAxis dataKey="name" type="category" width={155} tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Bar dataKey="count" fill={NAVY} radius={[0, 4, 4, 0]} name="Cases" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Risk Score Analysis by Case</CardTitle>
            <CardDescription>Risk score compared with key evidence signals</CardDescription>
          </CardHeader>
          <CardContent>
            {riskDistribution.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-16">No cases yet</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={riskDistribution} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.account ?? "Case"}
                    formatter={(value: any, name: any) => [`${Number(value).toFixed(0)}`, name]}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="risk" fill={RED} name="Risk Score" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="velocity" fill={NAVY} name="Velocity" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="structuring" fill={ORANGE} name="Structuring" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">30-Day Transaction Trend</CardTitle>
            <CardDescription>Daily transaction volume and detected suspicious activity</CardDescription>
          </CardHeader>
          <CardContent>
            {trendLoading || trendData.length === 0 ? (
              <div className="h-[260px] flex items-center justify-center text-sm text-slate-400">
                No transaction trend data available yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trendData} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={Math.max(0, Math.floor(trendData.length / 6) - 1)} tickFormatter={formatTrendDate} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    labelFormatter={formatTrendDate}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Area dataKey="count" stroke={NAVY} fill="#EBF0F8" name="Transactions" strokeWidth={2} />
                  <Area dataKey="fraud" stroke={RED} fill="#FDECEA" name="Suspicious" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="p-3 rounded border border-slate-200 bg-slate-50">
                <p className="text-xs text-slate-500">Average pipeline time</p>
                <p className="text-lg font-bold text-slate-900 mt-0.5">{avgProcessing.toFixed(1)}s</p>
              </div>
              <div className="p-3 rounded border border-slate-200 bg-slate-50">
                <p className="text-xs text-slate-500">Cases awaiting review</p>
                <p className="text-lg font-bold text-slate-900 mt-0.5">{strsPending}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
        {[
          { label: "Total Cases", value: totalCases, color: NAVY },
          { label: "Average Risk", value: `${avgRisk}/100`, color: RED },
          { label: "FATF Typology Types", value: uniqueTypes, color: ORANGE },
          { label: "STRs Pending Review", value: strsPending, color: GREEN },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded border border-slate-200 p-4 text-center">
            <p className="text-xs text-slate-500 mb-1">{label}</p>
            <p className="text-2xl font-bold" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
