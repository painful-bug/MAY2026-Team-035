import React, { useEffect, useState } from 'react';
import { Phone, RotateCw, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import OnboardingLayout from '../../components/onboarding/OnboardingLayout';
import OtpInput from '../../components/onboarding/OtpInput';
import { ONBOARDING_STEPS } from '../../data/onboarding';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { ASSOCIATION_CREATION_STATUS } from '../../store/slices/createOnboardingCompletionSlice';
import { useAppStore } from '../../store/appStore';
import { useAuthStore } from '../../store/authStore';
import { useOnboardingStore } from '../../store/onboardingStore';
import { formatPhoneNumber } from '../../utils/phone';

export default function OnboardingOtpPage() {
  const navigate = useNavigate();
  const currentPhone = useAuthStore((state) => state.currentPhone);
  const adminPhone = useOnboardingStore(
    (state) => state.adminProfile.phone
  );
  const creationStatus = useOnboardingStore(
    (state) => state.associationCreationStatus
  );
  const setOnboardingStep = useOnboardingStore(
    (state) => state.setOnboardingStep
  );
  const createAssociation = useOnboardingStore(
    (state) => state.createAssociation
  );
  const showToast = useAppStore((state) => state.showToast);
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const isCreating = creationStatus === ASSOCIATION_CREATION_STATUS.CREATING;
  const phone = adminPhone || currentPhone;

  useEffect(() => {
    setOnboardingStep(ONBOARDING_STEPS.ONBOARDING_OTP);
  }, [setOnboardingStep]);

  const handleOtpChange = (value) => {
    setOtp(value);
    setError('');
  };

  const handleBack = () => {
    setOnboardingStep(ONBOARDING_STEPS.ADMIN_PROFILE);
    navigate(AUTH_ROUTES.ADMIN_PROFILE);
  };

  const handleResend = () => {
    showToast('A new mock OTP has been sent successfully.', 'success');
  };

  const handleCreateAssociation = async () => {
    if (!/^\d{6}$/.test(otp)) {
      setError('Enter the complete 6-digit OTP.');
      return;
    }

    const result = await createAssociation(otp);

    if (!result.success) {
      setError(result.message);
      return;
    }

    navigate(AUTH_ROUTES.ONBOARDING_SUCCESS, { replace: true });
  };

  return (
    <OnboardingLayout
      currentStep={ONBOARDING_STEPS.ONBOARDING_OTP}
      title="Verify Your Phone Number"
      subtitle="Enter the six-digit code to confirm the first administrator and create your association."
      onBack={handleBack}
      onNext={handleCreateAssociation}
      nextLabel={isCreating ? 'Creating Association...' : 'Create Association'}
      nextDisabled={isCreating}
    >
      <div className="mx-auto max-w-lg space-y-7 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 shadow-inner">
          <ShieldCheck className="h-7 w-7" />
        </div>

        <div className="space-y-2">
          <p className="text-sm font-bold text-slate-700">
            Enter the code sent to
          </p>
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-extrabold text-slate-800">
            <Phone className="h-4 w-4 text-indigo-500" />
            {formatPhoneNumber(phone)}
          </div>
        </div>

        <div className="space-y-3">
          <OtpInput value={otp} onChange={handleOtpChange} hasError={Boolean(error)} />
          {error && (
            <p role="alert" className="text-xs font-semibold text-rose-600">
              {error}
            </p>
          )}
          <p className="text-[11px] font-medium text-slate-400">
            Prototype mode accepts any six-digit code.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2 text-xs font-semibold text-slate-500">
          <span>Didn't receive the code?</span>
          <button
            type="button"
            onClick={handleResend}
            className="inline-flex items-center gap-1.5 font-bold text-indigo-600 transition-colors hover:text-indigo-700"
          >
            <RotateCw className="h-3.5 w-3.5" />
            Resend OTP
          </button>
        </div>
      </div>
    </OnboardingLayout>
  );
}
