import React from 'react';
import { ArrowLeft, ArrowRight, Building2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ONBOARDING_CONFIG } from '../../data/onboarding';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import ProgressStepper from './ProgressStepper';

export default function OnboardingLayout({
  currentStep,
  title,
  subtitle,
  children,
  onBack,
  onNext,
  backLabel = 'Back',
  nextLabel = 'Next',
  nextDisabled = false,
  showNext = true,
  maxWidthClass = 'max-w-3xl',
}) {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 font-sans sm:px-6 sm:py-12">
      <div className={`mx-auto space-y-6 ${maxWidthClass}`}>
        <div className="flex items-center justify-between gap-4 px-1">
          <Link to={AUTH_ROUTES.HOME} className="inline-flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-150">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <span className="block text-sm font-extrabold tracking-tight text-slate-900">
                HomeBandhu
              </span>
              <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Admin Onboarding
              </span>
            </div>
          </Link>
        </div>

        <div className="overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-xl shadow-slate-100 animate-slide-up">
          <div className="border-b border-slate-100 px-6 py-6 sm:px-8 sm:py-7">
            <ProgressStepper
              currentStep={currentStep}
              totalSteps={ONBOARDING_CONFIG.TOTAL_STEPS}
            />

            <div className="mt-6 space-y-2">
              <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
                {title}
              </h1>
              <p className="max-w-2xl text-sm font-medium leading-relaxed text-slate-500">
                {subtitle}
              </p>
            </div>
          </div>

          <main className="px-6 py-7 sm:px-8 sm:py-8">{children}</main>

          <div className="flex flex-col-reverse gap-3 border-t border-slate-100 bg-slate-50/50 px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-600 transition-all hover:border-slate-300 hover:bg-slate-50 sm:w-auto"
            >
              <ArrowLeft className="h-4 w-4" />
              {backLabel}
            </button>

            {showNext && (
              <button
                type="button"
                onClick={onNext}
                disabled={nextDisabled}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-indigo-300 sm:w-auto"
              >
                {nextLabel}
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
