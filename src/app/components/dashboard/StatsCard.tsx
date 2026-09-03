import { LucideIcon } from "lucide-react";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  icon: LucideIcon;
  trend?: string;
  trendUp?: boolean;
  color?: 'red' | 'orange' | 'green' | 'blue';
}

export function StatsCard({ title, value, subtitle, icon: Icon, trend, trendUp, color = 'blue' }: StatsCardProps) {
  const iconBg = {
    red:    { bg: "#FDECEA", color: "#C0392B" },
    orange: { bg: "#FEF3E7", color: "#D35400" },
    green:  { bg: "#E9F7EF", color: "#1A7A4A" },
    blue:   { bg: "#EBF0F8", color: "#1A3A6B" },
  };

  const borderLeft = {
    red:    "#C0392B",
    orange: "#D35400",
    green:  "#1A7A4A",
    blue:   "#1A3A6B",
  };

  const { bg, color: iconColor } = iconBg[color];

  return (
    <div
      className="bg-white rounded border border-slate-200 p-5 hover:shadow-md transition-shadow"
      style={{ borderLeft: `4px solid ${borderLeft[color]}` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-1">{title}</p>
          <p className="text-3xl font-bold text-slate-900">{value}</p>
        </div>
        <div className="p-2.5 rounded" style={{ background: bg }}>
          <Icon className="w-5 h-5" style={{ color: iconColor }} />
        </div>
      </div>
      <p className="text-xs text-slate-500">{subtitle}</p>
      {trend && (
        <p className={`text-xs mt-1.5 font-medium ${trendUp ? 'text-red-600' : 'text-green-600'}`}>
          {trend}
        </p>
      )}
    </div>
  );
}
