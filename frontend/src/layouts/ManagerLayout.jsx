import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Building2,
  LayoutDashboard,
  LogOut,
  MessageSquareWarning,
  UserPlus,
  Users,
  Wrench,
  X,
} from 'lucide-react';
import Header from '../components/layout/Header';
import { AUTH_ROUTES } from '../routes/authRoutes';
import { useApp } from '../store/useApp';

// The department manager's portal.
//
// **A separate layout from SecurityLayout rather than a third branch inside
// it.** That file already carries two navs behind an `isManager` flag, and the
// gate has screens this manager has no business seeing — a plumbing manager
// does not verify visitor passes or run a tanker log. A third branch would have
// meant every gate screen growing a condition for somebody who never opens it.
//
// What a manager gets is deliberately narrow: their own department's skills and
// their own team. Everything wider — creating departments, other departments,
// community settings — stays in the admin portal, because
// `can_manage_department` refuses it anyway and a screen whose writes 403 is
// worse than no screen.

export default function ManagerLayout() {
  const { currentUser, logout } = useApp();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const base = AUTH_ROUTES.MANAGER_DASHBOARD;

  // **Hiring is here now.** It shipped without a tab and that was recorded as
  // `docs/potential issues/14` rather than left silent: the endpoints have
  // accepted a manager since `0035`, and the only obstacle was that
  // `DepartmentHiring.jsx` carried four hardcoded `/admin/…` links which would
  // each have bounced a manager back here. Those links now come from
  // `usePortalScope`, so one screen serves all three portals and the issue is
  // closed.
  //
  // The department id is in the path rather than implied by the session, so
  // that the URL has the same shape under every portal. It comes from the
  // session here because the nav is built before any route has supplied one.
  const departmentId = currentUser?.departmentId || null;

  const navItems = [
    { name: 'Overview', path: base, icon: LayoutDashboard, end: true },
    { name: 'Skills', path: `${base}/skills`, icon: Wrench },
    { name: 'Complaints', path: `${base}/complaints`, icon: MessageSquareWarning },
    { name: 'Team', path: `${base}/team`, icon: Users },
    // A manager with no department cannot be given a hiring link, because
    // there is no department for it to name. `can_manage_department` treats a
    // null `department_id` as "manages any", which is a decision for the admin
    // portal rather than a URL this nav can invent.
    ...(departmentId
      ? [{
        name: 'Hiring',
        path: `${base}/departments/${departmentId}/hiring`,
        icon: UserPlus,
      }]
      : []),
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
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-extrabold">HomeBandhu</p>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                Department
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
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/15 text-indigo-300">
                <Building2 className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-extrabold">{currentUser?.name}</p>
                {/* The department's *name* is deliberately not printed here.
                    The session carries `membership.department_id` and no name,
                    and inventing one from a stale local list is how
                    SecurityLayout ended up showing " · Main Gate" to every
                    guard. The overview page reads the real one. */}
                <p className="mt-0.5 truncate text-[10px] font-semibold text-slate-400">
                  Department manager
                </p>
              </div>
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
