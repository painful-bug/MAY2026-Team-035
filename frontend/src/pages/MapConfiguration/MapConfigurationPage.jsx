import React, { useEffect } from 'react';
import { Building2, House } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
// WebP, not the original 3.8 MB PNG (2026-08-27): this step is also
// `lazy()`-loaded at the route level (`App.jsx`), so the image only ever
// downloads for a visitor who reaches the onboarding map step — but it was
// still the single heaviest asset in the app once they did.
import onboardingMap from '../../assets/onboarding-map.webp';
import OnboardingLayout from '../../components/onboarding/OnboardingLayout';
import InstructionPanel from '../../components/onboarding/map/InstructionPanel';
import LocationList from '../../components/onboarding/map/LocationList';
import MapCard from '../../components/onboarding/map/MapCard';
import MapMarker from '../../components/onboarding/map/MapMarker';
import {
  COMMUNITY_TYPES,
  ONBOARDING_STEPS,
} from '../../data/onboarding';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useOnboardingStore } from '../../store/onboardingStore';

export default function MapConfigurationPage() {
  const navigate = useNavigate();
  const communityType = useOnboardingStore((state) => state.communityType);
  const blocks = useOnboardingStore((state) => state.blocks);
  const villas = useOnboardingStore((state) => state.villas);
  const blockLocations = useOnboardingStore((state) => state.blockLocations);
  const villaLocations = useOnboardingStore((state) => state.villaLocations);
  const currentSelectedBlock = useOnboardingStore(
    (state) => state.currentSelectedBlock
  );
  const currentSelectedVilla = useOnboardingStore(
    (state) => state.currentSelectedVilla
  );
  const setOnboardingStep = useOnboardingStore(
    (state) => state.setOnboardingStep
  );
  const initializeMapSelection = useOnboardingStore(
    (state) => state.initializeMapSelection
  );
  const selectBlock = useOnboardingStore((state) => state.selectBlock);
  const selectVilla = useOnboardingStore((state) => state.selectVilla);
  const setSelectedBlockLocation = useOnboardingStore(
    (state) => state.setSelectedBlockLocation
  );
  const setSelectedVillaLocation = useOnboardingStore(
    (state) => state.setSelectedVillaLocation
  );
  const completeMapStep = useOnboardingStore(
    (state) => state.completeMapStep
  );

  useEffect(() => {
    setOnboardingStep(ONBOARDING_STEPS.MAP_CONFIGURATION);
    initializeMapSelection();
  }, [initializeMapSelection, setOnboardingStep]);

  const apartmentMode = communityType === COMMUNITY_TYPES.APARTMENT;
  const units = apartmentMode ? blocks : villas;
  const locations = apartmentMode ? blockLocations : villaLocations;
  const selectedUnitId = apartmentMode
    ? currentSelectedBlock
    : currentSelectedVilla;
  const selectUnit = apartmentMode ? selectBlock : selectVilla;
  const setSelectedUnitLocation = apartmentMode
    ? setSelectedBlockLocation
    : setSelectedVillaLocation;
  const configuredCount = units.filter((unit) => locations[unit.id]).length;
  const selectedUnit = units.find((unit) => unit.id === selectedUnitId);
  const configurationComplete = configuredCount === units.length;
  const unitName = apartmentMode ? 'block' : 'villa';
  const unitPlural = apartmentMode ? 'apartment blocks' : 'villas';
  const unnamedLabel = apartmentMode ? 'Unnamed Block' : 'Unnamed Villa';

  const handleBack = () => {
    setOnboardingStep(ONBOARDING_STEPS.ASSOCIATION_DETAILS);
    navigate(AUTH_ROUTES.ASSOCIATION_REGISTRATION);
  };

  const handleNext = () => {
    if (completeMapStep()) {
      navigate(AUTH_ROUTES.FEATURE_CONFIGURATION);
    }
  };

  const instructionTitle = configurationComplete
    ? `All ${unitPlural} are configured`
    : selectedUnit
      ? `Place ${selectedUnit.name || `the selected ${unitName}`}`
      : `Select a ${unitName}`;

  const instructionDescription = configurationComplete
    ? `You can select a configured ${unitName} to adjust its marker, or continue to the next step.`
    : selectedUnit
      ? `Click on the map to place a marker for this ${unitName}.`
      : `Choose a ${unitName} from the list before clicking on the map.`;

  return (
    <OnboardingLayout
      currentStep={ONBOARDING_STEPS.MAP_CONFIGURATION}
      title="Configure your community map"
      subtitle={`Place each ${unitName} on the simulated map. Select a ${unitName}, then click its approximate location.`}
      onBack={handleBack}
      onNext={handleNext}
      nextDisabled={!configurationComplete}
      maxWidthClass="max-w-6xl"
    >
      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-5">
            <div className="mb-4 flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                {apartmentMode ? (
                  <Building2 className="h-4 w-4" />
                ) : (
                  <House className="h-4 w-4" />
                )}
              </div>
              <div>
                <h2 className="text-sm font-extrabold text-slate-800">
                  {apartmentMode ? 'Apartment Blocks' : 'Villa List'}
                </h2>
                <p className="mt-1 text-[11px] font-medium leading-relaxed text-slate-500">
                  {configuredCount} of {units.length} configured
                </p>
              </div>
            </div>

            <LocationList
              units={units}
              locations={locations}
              selectedUnitId={selectedUnitId}
              unnamedLabel={unnamedLabel}
              onSelect={selectUnit}
            />
          </div>

          <InstructionPanel
            title={instructionTitle}
            description={instructionDescription}
            complete={configurationComplete}
          />
        </aside>

        <MapCard
          imageSrc={onboardingMap}
          onMapClick={setSelectedUnitLocation}
        >
          {units.map((unit) =>
            locations[unit.id] ? (
              <MapMarker
                key={unit.id}
                point={locations[unit.id]}
                label={unit.name || unnamedLabel}
              />
            ) : null
          )}
        </MapCard>
      </div>
    </OnboardingLayout>
  );
}
