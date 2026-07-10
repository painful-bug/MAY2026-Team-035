import React, { useEffect } from 'react';
import { Info, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import FeatureModuleCard from '../../components/onboarding/FeatureModuleCard';
import OnboardingLayout from '../../components/onboarding/OnboardingLayout';
import { ONBOARDING_STEPS } from '../../data/onboarding';
import { onboardingModules } from '../../data/onboardingModules';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useOnboardingStore } from '../../store/onboardingStore';

export default function FeatureConfigurationPage() {
  const navigate = useNavigate();
  const enabledModules = useOnboardingStore((state) => state.enabledModules);
  const toggleModule = useOnboardingStore((state) => state.toggleModule);
  const setOnboardingStep = useOnboardingStore(
    (state) => state.setOnboardingStep
  );
  const completeFeatureStep = useOnboardingStore(
    (state) => state.completeFeatureStep
  );

  useEffect(() => {
    setOnboardingStep(ONBOARDING_STEPS.FEATURE_CONFIGURATION);
  }, [setOnboardingStep]);

  const handleBack = () => {
    setOnboardingStep(ONBOARDING_STEPS.MAP_CONFIGURATION);
    navigate(AUTH_ROUTES.MAP_CONFIGURATION);
  };

  const handleNext = () => {
    completeFeatureStep();
    navigate(AUTH_ROUTES.ADMIN_PROFILE);
  };

  return (
    <OnboardingLayout
      currentStep={ONBOARDING_STEPS.FEATURE_CONFIGURATION}
      title="Customize your HomeBandhu workspace"
      subtitle="Choose the modules your association needs today. You can enable additional capabilities as your community grows."
      onBack={handleBack}
      onNext={handleNext}
      maxWidthClass="max-w-6xl"
    >
      <div className="space-y-6">
        <div className="flex flex-col gap-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs font-extrabold text-indigo-950">
                Build your ideal workspace
              </p>
              <p className="mt-1 text-[11px] font-medium leading-relaxed text-indigo-700">
                Select a card to enable or disable that module for your association.
              </p>
            </div>
          </div>
          <span className="shrink-0 rounded-full bg-white px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-600 shadow-sm">
            {enabledModules.length} of {onboardingModules.length} enabled
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {onboardingModules.map((module) => (
            <FeatureModuleCard
              key={module.id}
              module={module}
              enabled={enabledModules.includes(module.id)}
              onToggle={toggleModule}
            />
          ))}
        </div>

        <div className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-slate-600">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
          <p className="text-xs font-semibold leading-relaxed">
            These features can be changed later from the Admin Settings page.
          </p>
        </div>
      </div>
    </OnboardingLayout>
  );
}
