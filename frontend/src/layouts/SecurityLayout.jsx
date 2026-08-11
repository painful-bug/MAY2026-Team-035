import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Building2,
  CalendarClock,
  ClipboardList,
  Download,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  ScanLine,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react';
import Header from '../components/layout/Header';
import { AUTH_ROUTES } from '../routes/authRoutes';
import { useApp } from '../store/useApp';

export default function SecurityLayout() {
  const { currentUser, logout } = useApp();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isManager = currentUser?.role === 'SecurityManager';
  const basePath = isManager
    ? AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD
    : AUTH_ROUTES.SECURITY_DASHBOARD;
  // Two navs over one layout. The guard's starts at the barrier because that is
  // where they stand; the manager's starts at the overview because they do not.
  const navItems = isManager
    ? [
        { name: 'Overview', path: basePath, icon: LayoutDashboard, end: true },
        { name: 'Roster', path: `${basePath}/roster`, icon: CalendarClock },
        { name: 'Gate', path: `${basePath}/gate`, icon: ScanLine },
        { name: 'Registers', path: `${basePath}/registers`, icon: ClipboardList },
        { name: 'Incidents', path: `${basePath}/incidents`, icon: ShieldAlert },
        { name: 'Exports', path: `${basePath}/exports`, icon: Download },
        // No "Manage Staff" entry: hiring, ranks and departures live in the
        // admin portal's department screens, which are the real roster. The
        // demo's local staff array here was a second, disagreeing copy.
        { name: 'Emergency', path: `${basePath}/emergency`, icon: LifeBuoy },
      ]
    : [
        { name: 'Gate', path: basePath, icon: ScanLine, end: true },
        { name: 'Registers', path: `${basePath}/registers`, icon: ClipboardList },
        { name: 'Incidents', path: `${basePath}/incidents`, icon: ShieldAlert },
        { name: 'Shifts', path: `${basePath}/shifts`, icon: CalendarClock },
        { name: 'Emergency', path: `${basePath}/emergency`, icon: LifeBuoy },
      ];

  const handleLogout = () => {
    void logout();
    navigate(AUTH_ROUTES.RESIDENT_LANDING);
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-[60] flex w-64 flex-col border-r border-slate-800 bg-slate-950 text-white transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-extrabold">HomeBandhu</p>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                {isManager ? 'Security Management' : 'Security Operations'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-5 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400">
                <Building2 className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-extrabold">
                  {currentUser?.name}
                </p>
                {/* `staffRole` used to be printed here and `applicationUser()`
                    has never set it, so this line read " · Main Gate" for every
                    guard who ever saw it. The post a guard is on is a property
                    of their shift, not of their session — it is on the Shifts
                    screen, which reads it from the API. */}
                <p className="mt-0.5 truncate text-[10px] font-semibold text-slate-400">
                  {isManager ? 'Security management' : 'Gate operations'}
                </p>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-500/10 px-3 py-2 text-[10px] font-bold text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              {isManager ? 'Manager access' : 'On duty'}
            </div>
          </div>

          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-colors ${
                    isActive
                      ? 'border-l-4 border-amber-400 bg-indigo-600 text-white shadow-lg shadow-indigo-950'
                      : 'text-slate-400 hover:bg-white/5 hover:text-white'
                  }`
                }
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="border-t border-white/10 p-4">
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2.5 text-xs font-bold text-slate-300 hover:border-rose-400/30 hover:bg-rose-500/10 hover:text-rose-300"
          >
            <LogOut className="h-4 w-4" />
            {/* Was "End Shift & Logout", which ended no shift. Ending a shift
                is now a real PATCH on the Shifts screen; this only logs out. */}
            Logout
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
