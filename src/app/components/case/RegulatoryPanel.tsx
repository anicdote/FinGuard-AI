import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Scale, AlertTriangle } from "lucide-react";
import type { RegulatoryFindings } from "../../types/investigation";

interface RegulatoryPanelProps {
  regulatory: RegulatoryFindings | null | undefined;
}

export function RegulatoryPanel({ regulatory }: RegulatoryPanelProps) {
  const typologies = regulatory?.fatfTypologies ?? [];
  const pmlaSections = regulatory?.pmlaSections ?? [];
  const confidence = regulatory?.regulatoryConfidence;
  const strRequired = regulatory?.strRequired;
  const fiuReportable = regulatory?.fiuIndReportable;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Regulatory Assessment (Agent 4)</CardTitle>
              <CardDescription>FATF typology mapping &amp; PMLA 2002 citations</CardDescription>
            </div>
            <div className="flex gap-2">
              {fiuReportable && <Badge variant="destructive">FIU-IND Reportable</Badge>}
              {strRequired && <Badge className="bg-[#C0392B] text-white">STR Required</Badge>}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {typologies.length === 0 ? (
            <p className="text-sm text-slate-400 py-4 text-center">
              Regulatory assessment was not run for this case — risk was below the planner's
              threshold, or no network findings triggered Agent 4.
            </p>
          ) : (
            <div className="space-y-3">
              {typologies.map((t) => (
                <div key={t.code} className="p-4 rounded-lg border" style={{ background: "#FDECEA", borderColor: "#F5C6C2" }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: "#C0392B" }} />
                      <div>
                        <p className="text-sm font-semibold" style={{ color: "#7B241C" }}>
                          {t.name} <span className="font-normal text-xs text-red-700">({t.code})</span>
                        </p>
                        <p className="text-xs text-red-800 mt-1">{t.description}</p>
                        <p className="text-xs text-red-700 mt-1.5 flex items-center gap-1">
                          <Scale className="w-3 h-3" /> PMLA 2002 — {t.pmla}
                        </p>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-lg font-bold" style={{ color: "#C0392B" }}>
                        {(t.confidence * 100).toFixed(0)}%
                      </p>
                      <p className="text-[10px] text-red-700">confidence</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">PMLA 2002 Sections Cited</CardTitle>
        </CardHeader>
        <CardContent>
          {pmlaSections.length === 0 ? (
            <p className="text-sm text-slate-400">None cited.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {pmlaSections.map((s) => (
                <Badge key={s} variant="outline">{s}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Regulatory Confidence</CardTitle>
        </CardHeader>
        <CardContent>
          {typeof confidence === "number" ? (
            <>
              <p className="text-2xl font-bold text-slate-900">{(confidence * 100).toFixed(0)}%</p>
              <div className="w-full bg-slate-200 rounded-full h-2 mt-2">
                <div className="h-2 rounded-full bg-[#1A3A6B]" style={{ width: `${Math.min(confidence * 100, 100)}%` }} />
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-400">Not available.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
