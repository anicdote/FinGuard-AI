import { Outlet, Link, useLocation } from "react-router";
import { Shield, LayoutDashboard, BarChart3, Activity, LogOut, User } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function RootLayout() {
  const location = useLocation();
  const { user, logout } = useAuth();
  
  const navItems = [
    { path: "/", icon: LayoutDashboard, label: "Dashboard" },
    { path: "/analytics", icon: BarChart3, label: "Analytics" },
  ];
  
  return (
    <div className="min-h-screen bg-slate-100">
      <header style={{ background: "#1A3A6B" }} className="text-white shadow-md">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-white/10 p-2 rounded">
                <Shield className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">FinGuard AI</h1>
                <p className="text-xs uppercase tracking-widest" style={{ color: "#93B4D4" }}>
                  Autonomous Financial Crime Investigation
                </p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full" style={{ background: "rgba(26,122,74,0.35)", border: "1px solid rgba(120,220,160,0.35)" }}>
                <Activity className="w-3.5 h-3.5 text-green-200" />
                <span className="text-xs text-green-100 font-medium">Investigation engine online</span>
              </div>
              <div className="text-xs" style={{ color: "#93B4D4" }}>
                PMLA 2002 &nbsp;·&nbsp; FIU-IND aligned
              </div>
              {user && (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-xs" style={{ color: "#93B4D4" }}>
                    <User className="w-3.5 h-3.5" />
                    <span>{user.name}</span>
                    <span className="px-1.5 py-0.5 rounded text-white text-xs font-medium uppercase" style={{ background: "rgba(255,255,255,0.15)" }}>{user.role}</span>
                  </div>
                  <button
                    onClick={logout}
                    className="flex items-center gap-1 text-xs px-2 py-1 rounded hover:bg-white/10 transition-colors"
                    style={{ color: "#93B4D4" }}
                  >
                    <LogOut className="w-3 h-3" /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      
      <nav className="bg-white border-b border-slate-200 shadow-sm">
        <div className="container mx-auto px-6">
          <div className="flex gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 px-5 py-3 border-b-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-[#1A3A6B] text-[#1A3A6B]'
                      : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </nav>
      
      <main><Outlet /></main>
      
      <footer className="bg-white border-t border-slate-200 mt-12">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <p>FinGuard AI © 2026 &nbsp;|&nbsp; PMLA 2002 &amp; FIU-IND-aligned investigation workflow</p>
            <p>Multi-Agent Pipeline v2.1 &nbsp;|&nbsp; Last Updated: {new Date().toLocaleDateString()}</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
