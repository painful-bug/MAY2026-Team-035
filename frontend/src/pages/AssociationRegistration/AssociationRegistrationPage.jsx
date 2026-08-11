import React, { useEffect, useState } from 'react';
import { Building2, House, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import CommunityUnitInput from '../../components/onboarding/CommunityUnitInput';
import LocationCoordinatesInput from '../../components/common/LocationCoordinatesInput';
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
  const addressLine1 = useOnboardingStore((state) => state.addressLine1);
  const addressLine2 = useOnboardingStore((state) => state.addressLine2);
  const city = useOnboardingStore((state) => state.city);
  const stateName = useOnboardingStore((state) => state.state);
  const postalCode = useOnboardingStore((state) => state.postalCode);
  const countryCode = useOnboardingStore((state) => state.countryCode);
  const latitude = useOnboardingStore((state) => state.latitude);
  const longitude = useOnboardingStore((state) => state.longitude);
  const setCommunityCoordinates = useOnboardingStore((state) => state.setCommunityCoordinates);
  const blocks = useOnboardingStore((state) => state.blocks);
  const villas = useOnboardingStore((state) => state.villas);
  const setAssociationName = useOnboardingStore(
    (state) => state.setAssociationName
  );
  const setCommunityType = useOnboardingStore(
    (state) => state.setCommunityType
  );
  const setAddressField = useOnboardingStore((state) => state.setAddressField);
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

  const handleAddressChange = (field) => (event) => {
    setAddressField(field, event.target.value);
    clearError(field);
  };

  const handleBack = () => {
    resetOnboarding();
    navigate(`${AUTH_ROUTES.GET_STARTED}?tab=create`, { replace: true });
  };

  const handleNext = () => {
    const validationErrors = validateAssociationDetails({
      associationName,
      addressLine1,
      city,
      state: stateName,
      postalCode,
      countryCode,
      latitude,
      longitude,
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

        <SectionCard
          icon={Building2}
          title="Association address"
          description="This helps residents identify the correct community when they search."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-[11px] font-bold uppercase tracking-wider text-slate-500 sm:col-span-2">
              Address line 1
              <input value={addressLine1} onChange={handleAddressChange('addressLine1')} aria-invalid={Boolean(errors.addressLine1)} className="block w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-500" placeholder="12 Palm Grove Road" />
              {errors.addressLine1 ? <span className="block normal-case text-xs text-rose-600">{errors.addressLine1}</span> : null}
            </label>
            <label className="space-y-2 text-[11px] font-bold uppercase tracking-wider text-slate-500 sm:col-span-2">
              Address line 2 <span className="text-slate-400">(optional)</span>
              <input value={addressLine2} onChange={handleAddressChange('addressLine2')} className="block w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-500" placeholder="Near the community park" />
            </label>
            {[
              ['city', 'City', city, errors.city],
              ['state', 'State', stateName, errors.state],
              ['postalCode', 'Postal code', postalCode, errors.postalCode],
              ['countryCode', 'Country code', countryCode, errors.countryCode],
            ].map(([field, label, value, error]) => (
              <label key={field} className="space-y-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                {label}
                <input value={value} onChange={handleAddressChange(field)} aria-invalid={Boolean(error)} className="block w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-500" />
                {error ? <span className="block normal-case text-xs text-rose-600">{error}</span> : null}
              </label>
            ))}
          </div>
        </SectionCard>

        <LocationCoordinatesInput
          value={{ latitude, longitude }}
          onChange={(coordinates) => {
            setCommunityCoordinates(coordinates);
            clearError('location');
          }}
          idPrefix="community-onboarding"
          required
        />
        {errors.location ? <p role="alert" className="text-xs font-semibold text-rose-600">{errors.location}</p> : null}

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
