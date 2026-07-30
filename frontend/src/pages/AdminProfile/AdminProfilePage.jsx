import React, { useEffect, useState } from 'react';
import {
  BadgeCheck,
  Camera,
  Home,
  Mail,
  UserRound,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import OnboardingLayout from '../../components/onboarding/OnboardingLayout';
import ProfileImageUploader from '../../components/onboarding/ProfileImageUploader';
import SectionCard from '../../components/onboarding/SectionCard';
import { adminDesignations } from '../../data/adminDesignations';
import { COMMUNITY_TYPES, ONBOARDING_STEPS } from '../../data/onboarding';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useOnboardingStore } from '../../store/onboardingStore';
import { useAuthStore } from '../../store/authStore';
import { validateAdminProfile } from '../../utils/adminProfile';

const getInputClassName = (hasError, readOnly = false) =>
  `w-full rounded-xl border py-3 pl-10 pr-4 text-sm font-medium outline-none transition-all ${
    readOnly
      ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-500'
      : `bg-white text-slate-700 placeholder:text-slate-400 ${
          hasError
            ? 'border-rose-300 focus:border-rose-400'
            : 'border-slate-200 focus:border-indigo-500'
        }`
  }`;

export default function AdminProfilePage() {
  const navigate = useNavigate();
  const communityType = useOnboardingStore((state) => state.communityType);
  const blocks = useOnboardingStore((state) => state.blocks);
  const villas = useOnboardingStore((state) => state.villas);
  const adminProfile = useOnboardingStore((state) => state.adminProfile);
  const setAdminProfileField = useOnboardingStore(
    (state) => state.setAdminProfileField
  );
  const identity = useAuthStore((state) => state.sessionContext?.identity);
  const setAdminProfileImage = useOnboardingStore(
    (state) => state.setAdminProfileImage
  );
  const setOnboardingStep = useOnboardingStore(
    (state) => state.setOnboardingStep
  );
  const completeAdminProfileStep = useOnboardingStore(
    (state) => state.completeAdminProfileStep
  );
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setOnboardingStep(ONBOARDING_STEPS.ADMIN_PROFILE);
  }, [setOnboardingStep]);

  useEffect(() => {
    if (!adminProfile.email && identity?.email) {
      setAdminProfileField('email', identity.email);
    }
    if (!adminProfile.fullName && identity?.full_name) {
      setAdminProfileField('fullName', identity.full_name);
    }
  }, [adminProfile.email, adminProfile.fullName, identity, setAdminProfileField]);

  const handleFieldChange = (field) => (event) => {
    setAdminProfileField(field, event.target.value);
    setErrors((currentErrors) => ({
      ...currentErrors,
      [field]: undefined,
    }));
  };

  const handleBack = () => {
    setOnboardingStep(ONBOARDING_STEPS.FEATURE_CONFIGURATION);
    navigate(AUTH_ROUTES.FEATURE_CONFIGURATION);
  };

  const handleNext = () => {
    const validationErrors = validateAdminProfile(adminProfile);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    completeAdminProfileStep();
    navigate(AUTH_ROUTES.ONBOARDING_REVIEW);
  };

  const apartmentMode = communityType === COMMUNITY_TYPES.APARTMENT;
  const unitLabel = apartmentMode ? 'Flat Number' : 'Villa Number';
  const unitPlaceholder = apartmentMode ? 'A-302' : 'Villa-17';
  const structures = apartmentMode ? blocks : villas;

  return (
    <OnboardingLayout
      currentStep={ONBOARDING_STEPS.ADMIN_PROFILE}
      title="Create the first administrator profile"
      subtitle="This administrator will also be registered as the first resident with association management privileges."
      onBack={handleBack}
      onNext={handleNext}
      maxWidthClass="max-w-4xl"
    >
      <div className="space-y-6">
        <section className="rounded-2xl border border-slate-100 bg-slate-50/60 p-5 sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Camera className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-slate-800">
                Profile Picture
              </h2>
              <p className="mt-1 text-xs font-medium text-slate-500">
                Add a photo or continue with generated initials.
              </p>
            </div>
          </div>
          <ProfileImageUploader
            fullName={adminProfile.fullName}
            profileImage={adminProfile.profileImage}
            onImageChange={setAdminProfileImage}
          />
        </section>

        <SectionCard
          icon={UserRound}
          title="Personal Information"
          description="Enter the administrator's name and optional association role."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label
                htmlFor="admin-full-name"
                className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
              >
                Full Name
              </label>
              <div className="relative">
                <UserRound className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  id="admin-full-name"
                  type="text"
                  value={adminProfile.fullName}
                  onChange={handleFieldChange('fullName')}
                  aria-invalid={Boolean(errors.fullName)}
                  placeholder="Aakash Deka"
                  className={getInputClassName(Boolean(errors.fullName))}
                />
              </div>
              {errors.fullName && (
                <p role="alert" className="text-xs font-semibold text-rose-600">
                  {errors.fullName}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <label
                htmlFor="admin-designation"
                className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
              >
                Designation <span className="text-slate-400">(Optional)</span>
              </label>
              <div className="relative">
                <BadgeCheck className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <select
                  id="admin-designation"
                  value={adminProfile.designation}
                  onChange={handleFieldChange('designation')}
                  className="w-full appearance-none rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm font-medium text-slate-700 outline-none transition-all focus:border-indigo-500"
                >
                  <option value="">Select designation</option>
                  {adminDesignations.map((designation) => (
                    <option key={designation} value={designation}>
                      {designation}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          icon={Mail}
          title="Contact Information"
          description="Email is used for contact information; Google remains the only sign-in method."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label
                htmlFor="admin-email"
                className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
              >
                Verified email
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  id="admin-email"
                  type="email"
                  value={adminProfile.email}
                  readOnly
                  aria-invalid={Boolean(errors.email)}
                  placeholder="admin@example.com"
                  className={getInputClassName(Boolean(errors.email), true)}
                />
              </div>
              {errors.email && (
                <p role="alert" className="text-xs font-semibold text-rose-600">
                  {errors.email}
                </p>
              )}
            </div>
          </div>
        </SectionCard>

        <SectionCard
          icon={Home}
          title="Residence Information"
          description="Connect this administrator to their resident home inside the association."
        >
          <div className="max-w-sm space-y-2">
            <label
              htmlFor="founder-structure"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
            >
              {apartmentMode ? 'Your block' : 'Your villa'}
            </label>
            <select
              id="founder-structure"
              value={adminProfile.founderStructureId}
              onChange={handleFieldChange('founderStructureId')}
              aria-invalid={Boolean(errors.founderStructureId)}
              className={getInputClassName(Boolean(errors.founderStructureId))}
            >
              <option value="">Select {apartmentMode ? 'a block' : 'a villa'}</option>
              {structures.map((structure) => (
                <option key={structure.id} value={structure.id}>{structure.name}</option>
              ))}
            </select>
            {errors.founderStructureId && <p role="alert" className="text-xs font-semibold text-rose-600">{errors.founderStructureId}</p>}
            <label
              htmlFor="admin-unit-number"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
            >
              {unitLabel}
            </label>
            <div className="relative">
              <Home className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="admin-unit-number"
                type="text"
                value={adminProfile.unitNumber}
                onChange={handleFieldChange('unitNumber')}
                aria-invalid={Boolean(errors.unitNumber)}
                placeholder={unitPlaceholder}
                className={getInputClassName(Boolean(errors.unitNumber))}
              />
            </div>
            {errors.unitNumber && (
              <p role="alert" className="text-xs font-semibold text-rose-600">
                {errors.unitNumber}
              </p>
            )}
          </div>
        </SectionCard>
        {errors.submit && <p role="alert" className="text-sm font-semibold text-rose-600">{errors.submit}</p>}
      </div>
    </OnboardingLayout>
  );
}
