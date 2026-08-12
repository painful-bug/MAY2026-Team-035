import { Building2, Search } from 'lucide-react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import JoinCommunityTab from '../../features/registration/components/JoinCommunityTab';
import { AUTH_ROUTES, homeRouteFor } from '../../routes/authRoutes';
import { useAuthStore } from '../../store/authStore';
import { useOnboardingStore } from '../../store/onboardingStore';

export default function GetStartedPage() {
  const [params, setParams] = useSearchParams();
  const context = useAuthStore((state) => state.sessionContext);
  const ready = useAuthStore((state) => state.isAuthReady);
  const setAdminProfile = useOnboardingStore((state) => state.setAdminProfile);
  const tab = params.get('tab') === 'join' ? 'join' : 'create';

  if (!ready) return <div className="flex min-h-screen items-center justify-center text-sm font-semibold text-slate-500">Restoring your session…</div>;
  if (!context?.identity) return <Navigate to={AUTH_ROUTES.REGISTER} replace />;
  if (context.membership || !context.onboarding_eligible) return <Navigate to={homeRouteFor(context)} replace />;

  const openCreate = () => {
    setAdminProfile({ fullName: context.identity.full_name || '', email: context.identity.email || '' });
    setParams({ tab: 'create' });
  };

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10 sm:px-6">
      <section className="mx-auto max-w-2xl rounded-3xl border border-slate-100 bg-white p-6 shadow-xl shadow-slate-100 sm:p-10">
        <span className="text-xs font-bold uppercase tracking-widest text-indigo-600">Welcome to HomeBandhu</span>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900">How would you like to get started?</h1>
        <p className="mt-2 text-sm font-medium text-slate-500">Your verified Google account is ready. Create a community as its founding administrator, or request access to an existing one.</p>
        <div role="tablist" className="mt-7 grid grid-cols-2 rounded-xl bg-slate-100 p-1">
          <button role="tab" aria-selected={tab === 'create'} onClick={openCreate} className={`rounded-lg px-3 py-2.5 text-sm font-bold ${tab === 'create' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500'}`}><Building2 className="mr-1.5 inline h-4 w-4" />Create a Community</button>
          <button role="tab" aria-selected={tab === 'join'} onClick={() => setParams({ tab: 'join' })} className={`rounded-lg px-3 py-2.5 text-sm font-bold ${tab === 'join' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500'}`}><Search className="mr-1.5 inline h-4 w-4" />Join a Community</button>
        </div>
        <div className="mt-7">
          {tab === 'create' ? (
            <div className="space-y-5 rounded-2xl border border-slate-100 bg-slate-50 p-6">
              <h2 className="text-lg font-extrabold text-slate-900">Set up your association</h2>
              <p className="text-sm font-medium leading-relaxed text-slate-600">Add the association address, blocks or villas, their map locations, enabled modules, and your administrator profile. You will review everything before HomeBandhu creates the community.</p>
              <Link to={AUTH_ROUTES.ASSOCIATION_REGISTRATION} className="inline-flex rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-sm">Start community setup</Link>
            </div>
          ) : <JoinCommunityTab />}
        </div>
      </section>
    </main>
  );
}
