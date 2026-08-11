import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Briefcase,
  CalendarDays,
  Clock,
  LogOut,
  MapPinned,
  Menu,
  MessageSquare,
  MessageSquareWarning,
  Settings,
  UserRound,
  Wrench,
  X,
} from 'lucide-react';
import { AUTH_ROUTES } from '../routes/authRoutes';
import { useAuthStore } from '../store/authStore';
import { workerApi } from '../features/worker/workerApi';
import NotificationBell from '../components/notifications/NotificationBell';

// Modelled on SecurityLayout.jsx, with two deliberate differences.
//
// It does NOT render components/layout/Header.jsx. That header searches
// notices, visitors and complaints out of the demo store, and a service person
// holds none of the three -- it would render an always-empty search box over an
// always-empty bell.
//
// And it does not read `currentUser`. `applicationUser()` returns null for
// anybody with no membership, which is precisely the service person who has
// registered and not yet been hired: the population these screens exist for.
// Identity comes from `sessionContext`, and what the portal shows is decided by
// `GET /worker/snapshot`, whose `provider: null` is the whole empty state.

const NAV = [
  { name: 'Dashboard', path: AUTH_ROUTES.WORKER_DASHBOARD, icon: Briefcase, end: true },
  { name: 'Calendar', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/calendar`, icon: CalendarDays },
  { name: 'Availability', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/availability`, icon: Clock },
  { name: 'Communities', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/communities`, icon: MapPinned },
  // Supervisors only in practice — the page itself checks the roster rank the
  // worker snapshot already carries, and tells a technician plainly that their
  // work arrives as jobs instead. It is in the nav for everyone because the
  // session carries no rank, and putting one there would mean editing the auth
  // owner's file so a menu item could be hidden.
  { name: 'Complaints', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/complaints`, icon: MessageSquareWarning },
  { name: 'Messages', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/messages`, icon: MessageSquare },
  { name: 'Profile', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/profile`, icon: UserRound },
  { name: 'Settings', path: `${AUTH_ROUTES.WORKER_DASHBOARD}/settings`, icon: Settings },
];

function AvailabilityToggle() {
  const queryClient = useQueryClient();
  const snapshot = useQuery({ queryKey: ['worker-snapshot'], queryFn: workerApi.snapshot });
  const provider = snapshot.data?.provider;
  const toggle = useMutation({
    mutationFn: (next) => workerApi.setAvailable(next),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['worker-snapshot'] }),
  });

  if (!provider) return null;
  const available = snapshot.data?.isAvailable ?? provider.isAvailable;

  return (
    <button
      type="button"
      disabled={toggle.isPending}
      onClick={() => toggle.mutate(!available)}
      className={`mt-3 flex w-full items-center justify-between rounded-lg px-3 py-2 text-[10px] font-bold transition-colors disabled:opacity-60 ${
        available
          ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
          : 'bg-slate-500/10 text-slate-400 hover:bg-slate-500/20'
      }`}
    >
      <span className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${available ? 'bg-emerald-400' : 'bg-slate-500'}`} />
        {available ? 'Taking work' : 'Not taking work'}
      </span>
      <span className="text-[9px] font-semibold uppercase tracking-wider opacity-70">
        {toggle.isPending ? '…' : 'Change'}
      </span>
    </button>
  );
}

export default function WorkerLayout() {
  const sessionContext = useAuthStore((state) => state.sessionContext);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const name = sessionContext?.identity?.full_name || sessionContext?.identity?.email || 'Service partner';

  const handleLogout = () => {
    void logout();
    navigate(AUTH_ROUTES.LOGIN);
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-[60] flex w-64 flex-col border-r border-slate-800 bg-slate-950 text-white transition-transform duration-300 lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600">
              <Wrench className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-extrabold">HomeBandhu</p>
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                Service Partner
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-5 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/15 text-indigo-300">
                <UserRound className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-extrabold">{name}</p>
                <p className="mt-0.5 truncate text-[10px] font-semibold text-slate-400">
                  {sessionContext?.identity?.email}
                </p>
              </div>
            </div>
            <AvailabilityToggle />
          </div>

          <nav className="space-y-1">
            {NAV.map((item) => (
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
        {/* Was lg:hidden and mobile-only. It stays on desktop now because the
            bell lives here — a worker whose leave was decided finds out from
            this feed, and a portal with no header had nowhere to hang it. */}
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-slate-100 bg-white px-4 sm:px-6">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <p className="text-sm font-extrabold text-slate-800">Service Partner</p>
          <div className="ml-auto">
            <NotificationBell />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
