import React, { useEffect, useState } from 'react';
import { Building2, House, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import CommunityUnitInput from '../../components/onboarding/CommunityUnitInput';
import OnboardingLayout from '../../components/onboarding/OnboardingLayout';
import SectionCard from '../../components/onboarding/SectionCard';
import SegmentedToggle from '../../components/onboarding/SegmentedToggle';
import {
  COMMUNITY_TYPES,
  ONBOARDING_CONFIG,
  ONBOARDING_STEPS,
  communityTypeOptions,
} from '../../data/onboarding';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useAuthStore } from '../../store/authStore';
import { useOnboardingStore } from '../../store/onboardingStore';
import {
  canAddBlock,
  canAddVilla,
  validateAssociationDetails,
} from '../../utils/onboarding';

export default function AssociationRegistrationPage() {
  const navigate = useNavigate();
  const associationName = useOnboardingStore((state) => state.associationName);
  const communityType = useOnboardingStore((state) => state.communityType);
  const blocks = useOnboardingStore((state) => state.blocks);
  const villas = useOnboardingStore((state) => state.villas);
  const setAssociationName = useOnboardingStore(
    (state) => state.setAssociationName
  );
  const setCommunityType = useOnboardingStore(
    (state) => state.setCommunityType
  );
  const updateBlock = useOnboardingStore((state) => state.updateBlock);
  const addBlock = useOnboardingStore((state) => state.addBlock);
  const removeBlock = useOnboardingStore((state) => state.removeBlock);
  const updateVilla = useOnboardingStore((state) => state.updateVilla);
  const addVilla = useOnboardingStore((state) => state.addVilla);
  const removeVilla = useOnboardingStore((state) => state.removeVilla);
  const completeAssociationStep = useOnboardingStore(
    (state) => state.completeAssociationStep
  );
  const setOnboardingStep = useOnboardingStore(
    (state) => state.setOnboardingStep
  );
  const resetOnboarding = useOnboardingStore(
    (state) => state.resetOnboarding
  );
  const resetAdminAuthentication = useAuthStore(
    (state) => state.resetAdminAuthentication
  );
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setOnboardingStep(ONBOARDING_STEPS.ASSOCIATION_DETAILS);
  }, [setOnboardingStep]);

  const clearError = (field) => {
    setErrors((currentErrors) => ({ ...currentErrors, [field]: undefined }));
  };

  const handleAssociationNameChange = (event) => {
    setAssociationName(event.target.value);
    clearError('associationName');
  };

  const handleCommunityTypeChange = (value) => {
    setCommunityType(value);
    clearError('blocks');
    clearError('villas');
  };

  const handleBack = () => {
    resetOnboarding();
    resetAdminAuthentication();
    navigate(AUTH_ROUTES.LOGIN, { replace: true });
  };

  const handleNext = () => {
    const validationErrors = validateAssociationDetails({
      associationName,
      communityType,
      blocks,
      villas,
    });

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    completeAssociationStep();
    navigate(AUTH_ROUTES.MAP_CONFIGURATION);
  };

  const apartmentSelected = communityType === COMMUNITY_TYPES.APARTMENT;
  const units = apartmentSelected ? blocks : villas;
  const updateUnit = apartmentSelected ? updateBlock : updateVilla;
  const addUnit = apartmentSelected ? addBlock : addVilla;
  const removeUnit = apartmentSelected ? removeBlock : removeVilla;
  const unitCanBeAdded = apartmentSelected
    ? canAddBlock(blocks)
    : canAddVilla(villas);
  const unitLabel = apartmentSelected ? 'Apartment block' : 'Villa';
  const unitName = apartmentSelected ? 'Block' : 'Villa';
  const unitPlural = apartmentSelected ? 'blocks' : 'villas';
  const maximumUnits = apartmentSelected
    ? ONBOARDING_CONFIG.MAX_BLOCKS
    : ONBOARDING_CONFIG.MAX_VILLAS;
  const unitError = apartmentSelected ? errors.blocks : errors.villas;

  return (
    <OnboardingLayout
      currentStep={ONBOARDING_STEPS.ASSOCIATION_DETAILS}
      title="Tell us about your association"
      subtitle="Start with the basic details that identify your community. You can refine operational settings in the upcoming steps."
      onBack={handleBack}
      onNext={handleNext}
    >
      <div className="space-y-6">
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-4">
            <label
              htmlFor="association-name"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
            >
              Association Name
            </label>
            <span className="text-[10px] font-semibold text-slate-400">
              {associationName.length} / 100
            </span>
          </div>
          <div className="relative">
            <Building2 className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              id="association-name"
              type="text"
              value={associationName}
              onChange={handleAssociationNameChange}
              maxLength={100}
              aria-invalid={Boolean(errors.associationName)}
              aria-describedby={
                errors.associationName ? 'association-name-error' : undefined
              }
              placeholder="Palm Grove Residency"
              className={`w-full rounded-xl border bg-slate-50 py-3 pl-10 pr-4 text-sm font-medium text-slate-700 outline-none transition-all placeholder:text-slate-400 focus:bg-white ${
                errors.associationName
                  ? 'border-rose-300 focus:border-rose-400'
                  : 'border-slate-200 focus:border-indigo-500'
              }`}
            />
          </div>
          {errors.associationName && (
            <p
              id="association-name-error"
              role="alert"
              className="text-xs font-semibold text-rose-600"
            >
              {errors.associationName}
            </p>
          )}
        </div>

        <SegmentedToggle
          label="Community Type"
          options={communityTypeOptions}
          value={communityType}
          onChange={handleCommunityTypeChange}
        />

        <SectionCard
          icon={apartmentSelected ? Building2 : House}
          title={apartmentSelected ? 'Apartment Blocks' : 'Villa List'}
          description={
            apartmentSelected
              ? 'Add every building or tower in your association. Block names can be edited at any time.'
              : 'Add every villa in your community. Villa names can be edited at any time.'
          }
        >
          <div className="space-y-3">
            {units.map((unit, index) => (
              <CommunityUnitInput
                key={unit.id}
                unit={unit}
                index={index}
                unitLabel={unitLabel}
                placeholderPrefix={unitName}
                canDelete={units.length > 1}
                onChange={updateUnit}
                onDelete={removeUnit}
              />
            ))}

            {unitError && (
              <p role="alert" className="text-xs font-semibold text-rose-600">
                {unitError}
              </p>
            )}

            <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={addUnit}
                disabled={!unitCanBeAdded}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-600 transition-colors hover:text-indigo-700 disabled:cursor-not-allowed disabled:text-slate-300"
              >
                <Plus className="h-4 w-4" />
                Add {unitName}
              </button>
              <span className="text-[10px] font-semibold text-slate-400">
                {units.length} of {maximumUnits} {unitPlural}
              </span>
            </div>
          </div>
        </SectionCard>
      </div>
    </OnboardingLayout>
  );
}
