import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Network } from "lucide-react";
import type { NetworkFindings } from "../../types/investigation";

interface NetworkGraphProps {
  networkData: NetworkFindings | null | undefined;
  accountName: string;
}

const RISK_COLOR: Record<string, string> = {
  critical: "#C0392B",
  high:     "#D35400",
  medium:   "#B7791F",
  low:      "#1A7A4A",
};

export function NetworkGraph({ networkData, accountName }: NetworkGraphProps) {
  const nodes       = networkData?.nodes ?? [];
  const edges       = networkData?.edges ?? [];
  const sccClusters = networkData?.sccClusters ?? [];
  const maxPagerank = networkData?.maxPagerank ?? 0;
  const centralNode = networkData?.centralNode ?? "";
  const nodeCount   = networkData?.nodeCount ?? nodes.length;
  const edgeCount   = networkData?.edgeCount ?? edges.length;

  const primary = nodes.find((n) => n.isPrimary) ?? nodes[0];
  const others  = nodes.filter((n) => n !== primary);

  // Lay nodes out in a circle around the primary account for the SVG view
  const mainNode = primary
    ? { id: primary.accountId, x: 250, y: 200, label: accountName || primary.accountId, isMain: true, level: primary.riskLevel }
    : null;

  const connectedNodes = others.slice(0, 12).map((node, idx) => {
    const angle  = (idx / Math.min(others.length, 12)) * 2 * Math.PI;
    const radius = 130;
    return {
      id:     node.accountId,
      x:      250 + Math.cos(angle) * radius,
      y:      200 + Math.sin(angle) * radius,
      label:  `…${String(node.accountId).slice(-6)}`,
      isMain: false,
      level:  node.riskLevel,
    };
  });

  const allNodes = mainNode ? [mainNode, ...connectedNodes] : connectedNodes;
  const idToNode = Object.fromEntries(allNodes.map((n) => [n.id, n]));

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Network Investigation (Agent 3)</CardTitle>
            <CardDescription>Transaction network &amp; PageRank centrality</CardDescription>
          </div>
          <Badge variant="outline">
            <Network className="w-3 h-3 mr-1" />
            {nodeCount} Account{nodeCount === 1 ? "" : "s"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* SVG Graph */}
          <div className="lg:col-span-2">
            {nodes.length === 0 ? (
              <div className="flex items-center justify-center h-[400px] bg-slate-50 rounded-lg border border-slate-200">
                <p className="text-sm text-slate-400 text-center px-6">
                  Network investigation was not run for this case — risk score was below the
                  planner's threshold for Agent 3.
                </p>
              </div>
            ) : (
              <div className="bg-slate-900 rounded-lg p-4 relative overflow-hidden" style={{ height: 400 }}>
                <svg width="100%" height="100%" viewBox="0 0 500 400">
                  {/* Edges */}
                  {edges.map((edge, idx) => {
                    const from = idToNode[edge.from];
                    const to   = idToNode[edge.to];
                    if (!from || !to) return null;
                    return (
                      <line
                        key={idx}
                        x1={from.x} y1={from.y}
                        x2={to.x}   y2={to.y}
                        stroke="#1A3A6B" strokeWidth="1.5" strokeOpacity="0.6"
                        strokeDasharray="4 2"
                      />
                    );
                  })}
                  {/* Nodes */}
                  {allNodes.map((node) => (
                    <g key={node.id}>
                      <circle
                        cx={node.x} cy={node.y}
                        r={node.isMain ? 24 : 14}
                        fill={node.isMain ? "#C0392B" : (RISK_COLOR[node.level as string] ?? "#1A3A6B")}
                        stroke={node.isMain ? "#E74C3C" : "#2980B9"}
                        strokeWidth="2"
                      />
                      <text
                        x={node.x} y={node.y + (node.isMain ? 36 : 24)}
                        textAnchor="middle"
                        fill="#CBD5E1"
                        fontSize={node.isMain ? "10" : "8"}
                      >
                        {node.label.length > 14 ? node.label.slice(0, 14) + "…" : node.label}
                      </text>
                      {node.isMain && (
                        <text x={node.x} y={node.y + 4} textAnchor="middle" fill="white" fontSize="8" fontWeight="bold">
                          MAIN
                        </text>
                      )}
                    </g>
                  ))}
                </svg>
                <div className="absolute top-3 right-3 flex items-center gap-3 text-xs text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-red-600 inline-block" /> Subject
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-blue-800 inline-block" /> Connected
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Stats panel */}
          <div className="space-y-4">
            <div className="p-4 rounded-lg border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 mb-1">Max PageRank</p>
              <p className="text-2xl font-bold text-slate-900">{(maxPagerank * 100).toFixed(1)}</p>
              <p className="text-xs text-slate-500 mt-1">Network centrality measure</p>
            </div>

            <div className="p-4 rounded-lg border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 mb-1">Central Node</p>
              <p className="text-sm font-bold text-slate-900 break-all">{centralNode || "—"}</p>
              <p className="text-xs text-slate-500 mt-1">Highest-PageRank account in this graph</p>
            </div>

            <div className="p-4 rounded-lg border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 mb-1">Nodes / Edges</p>
              <p className="text-2xl font-bold text-slate-900">{nodeCount} / {edgeCount}</p>
              <p className="text-xs text-slate-500 mt-1">Accounts &amp; transfers in this cluster</p>
            </div>

            {/* Node risk list */}
            {others.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-700 mb-2 uppercase tracking-wide">
                  Connected Accounts
                </p>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {others.slice(0, 15).map((node) => (
                    <div
                      key={node.accountId}
                      className="flex items-center justify-between p-2 rounded text-xs"
                      style={{ background: "#FEF3E7", border: "1px solid #FAD7A0" }}
                    >
                      <span className="text-slate-600 truncate max-w-[140px]">
                        …{String(node.accountId).slice(-8)}
                      </span>
                      <span className="font-semibold ml-2" style={{ color: RISK_COLOR[node.riskLevel] ?? "#D35400" }}>
                        {node.riskLevel} · {(node.riskScore * 100).toFixed(0)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SCC clusters */}
        {sccClusters.length > 0 && (
          <div className="mt-6 p-4 rounded-lg border border-red-200 bg-red-50">
            <p className="text-sm font-semibold text-red-900 mb-1">Cluster Summary</p>
            {sccClusters.map((c) => (
              <p key={c.clusterId} className="text-sm text-red-800">
                {c.clusterId}: {c.nodeCount} connected account{c.nodeCount === 1 ? "" : "s"}, average risk{" "}
                {(c.avgRisk * 100).toFixed(0)}/100.
              </p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
