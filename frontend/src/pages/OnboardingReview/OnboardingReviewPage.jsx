import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import OnboardingLayout from '../../components/onboarding/OnboardingLayout';
import { ONBOARDING_STEPS } from '../../data/onboarding';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { ASSOCIATION_CREATION_STATUS } from '../../store/slices/createOnboardingCompletionSlice';
import { useOnboardingStore } from '../../store/onboardingStore';

export default function OnboardingReviewPage() {
  const navigate = useNavigate();
  const state = useOnboardingStore();
  const [error, setError] = useState('');
  const structures = state.communityType === 'apartment' ? state.blocks : state.villas;
  const creating = state.associationCreationStatus === ASSOCIATION_CREATION_STATUS.CREATING;

  const create = async () => {
    setError('');
    const result = await state.createAssociation();
    if (result.success) navigate(AUTH_ROUTES.ONBOARDING_SUCCESS, { replace: true });
    else setError(result.message);
  };

  return (
    <OnboardingLayout
      currentStep={ONBOARDING_STEPS.REVIEW}
      title="Review your community setup"
      subtitle="HomeBandhu will create your community and active administrator membership together."
      onBack={() => navigate(AUTH_ROUTES.ADMIN_PROFILE)}
      onNext={create}
      nextLabel={creating ? 'Creating community…' : 'Create community'}
      nextDisabled={creating}
      maxWidthClass="max-w-4xl"
    >
      <div className="space-y-5 text-sm">
        <section className="rounded-2xl border border-slate-100 bg-slate-50 p-5">
          <h2 className="font-extrabold text-slate-900">Community</h2>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            <div><dt className="text-xs font-bold uppercase text-slate-400">Name</dt><dd className="font-semibold text-slate-700">{state.associationName}</dd></div>
            <div><dt className="text-xs font-bold uppercase text-slate-400">Type</dt><dd className="font-semibold capitalize text-slate-700">{state.communityType.replace('_', ' / ')}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs font-bold uppercase text-slate-400">Address</dt><dd className="font-semibold text-slate-700">{[state.addressLine1, state.addressLine2, state.city, state.state, state.postalCode, state.countryCode].filter(Boolean).join(', ')}</dd></div>
          </dl>
        </section>
        <section className="rounded-2xl border border-slate-100 bg-slate-50 p-5">
          <h2 className="font-extrabold text-slate-900">{state.communityType === 'apartment' ? 'Blocks' : 'Villas'}</h2>
          <p className="mt-2 text-slate-600">{structures.map((structure) => structure.name).join(', ')}</p>
        </section>
        <section className="rounded-2xl border border-slate-100 bg-slate-50 p-5">
          <h2 className="font-extrabold text-slate-900">Founding administrator</h2>
          <p className="mt-2 text-slate-600">{state.adminProfile.fullName} · {state.adminProfile.email} · {state.adminProfile.unitNumber}</p>
        </section>
        {error ? <p role="alert" className="text-sm font-semibold text-rose-600">{error}</p> : null}
      </div>
    </OnboardingLayout>
  );
}
