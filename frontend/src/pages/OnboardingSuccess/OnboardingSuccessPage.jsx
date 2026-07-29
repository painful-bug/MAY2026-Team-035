import React from 'react';
import { ArrowRight, Building2, CheckCircle2, Phone } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { COMMUNITY_TYPES } from '../../data/onboarding';
import { onboardingModules } from '../../data/onboardingModules';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useAppStore } from '../../store/appStore';
import { useOnboardingStore } from '../../store/onboardingStore';
import { useAuthStore } from '../../store/authStore';
import { formatPhoneNumber } from '../../utils/phone';

export default function OnboardingSuccessPage() {
  const navigate = useNavigate();
  const createdAssociation = useOnboardingStore(
    (state) => state.createdAssociation
  );
  const resetOnboarding = useOnboardingStore((state) => state.resetOnboarding);
  const createdAdmin = useOnboardingStore((state) => state.createdAdmin);
  const refreshSession = useAuthStore((state) => state.refreshSession);
  const showToast = useAppStore((state) => state.showToast);

  const enabledModuleNames = onboardingModules
    .filter((module) =>
      (createdAssociation?.enabledModules || []).includes(module.id)
    )
    .map((module) => module.name);
  const communityTypeLabel =
    createdAssociation?.communityType === COMMUNITY_TYPES.APARTMENT
      ? 'Apartment'
      : 'Layout / Villa';

  const handleGoToDashboard = async () => {
    try {
      await refreshSession();
      resetOnboarding();
      showToast('Association setup is complete.', 'success');
      navigate(AUTH_ROUTES.ADMIN_DASHBOARD, { replace: true });
    } catch {
      showToast('Your community was created. Please retry loading the dashboard.', 'error');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10 font-sans sm:px-6 sm:py-14">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-100">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <span className="block text-sm font-extrabold tracking-tight text-slate-900">
              HomeBandhu
            </span>
            <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Onboarding Complete
            </span>
          </div>
        </div>

        <main className="overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-xl shadow-slate-100 animate-slide-up">
          <div className="space-y-5 border-b border-slate-100 px-6 py-8 text-center sm:px-10 sm:py-10">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 shadow-inner">
              <CheckCircle2 className="h-10 w-10" />
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
                Welcome to HomeBandhu!
              </h1>
              <p className="text-sm font-medium text-slate-500">
                Your association has been successfully created.
              </p>
            </div>
          </div>

          <div className="space-y-6 px-6 py-7 sm:px-10 sm:py-8">
            <section className="rounded-2xl border border-slate-100 bg-slate-50/70 p-5 sm:p-6">
              <h2 className="mb-5 text-xs font-extrabold uppercase tracking-widest text-slate-500">
                Association Summary
              </h2>
              <dl className="grid gap-5 sm:grid-cols-2">
                <div>
                  <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Association Name
                  </dt>
                  <dd className="mt-1 text-sm font-extrabold text-slate-800">
                    {createdAssociation?.name || 'Your community'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Community Type
                  </dt>
                  <dd className="mt-1 text-sm font-extrabold text-slate-800">
                    {communityTypeLabel}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Number of {createdAssociation?.unitType || 'structures'}
                  </dt>
                  <dd className="mt-1 text-sm font-extrabold text-slate-800">
                    {createdAssociation?.unitCount ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Administrator Name
                  </dt>
                  <dd className="mt-1 text-sm font-extrabold text-slate-800">
                    {createdAdmin?.fullName || createdAdmin?.name || 'Administrator'}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Phone Number
                  </dt>
                  <dd className="mt-1 inline-flex items-center gap-2 text-sm font-extrabold text-slate-800">
                    <Phone className="h-4 w-4 text-indigo-500" />
                    {createdAdmin?.phone ? formatPhoneNumber(createdAdmin.phone) : 'Not provided'}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Enabled Modules
                  </dt>
                  <dd className="mt-2 flex flex-wrap gap-2">
                    {enabledModuleNames.length > 0 ? (
                      enabledModuleNames.map((moduleName) => (
                        <span
                          key={moduleName}
                          className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-[10px] font-bold text-indigo-700"
                        >
                          {moduleName}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs font-semibold text-slate-400">
                        No modules enabled
                      </span>
                    )}
                  </dd>
                </div>
              </dl>
            </section>

            <button
              type="button"
              onClick={handleGoToDashboard}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3.5 text-sm font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700"
            >
              Go to Admin Dashboard
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}
