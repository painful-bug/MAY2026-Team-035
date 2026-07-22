import React, { useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import AvailabilitySettingsCard from '../components/Settings/AvailabilitySettingsCard.jsx';
import BookingSettingsCard from '../components/Settings/BookingSettingsCard.jsx';
import GeneralSettingsCard from '../components/Settings/GeneralSettingsCard.jsx';
import MaintenanceSettingsCard from '../components/Settings/MaintenanceSettingsCard.jsx';
import PaymentSettingsCard from '../components/Settings/PaymentSettingsCard.jsx';
import SettingsFooter from '../components/Settings/SettingsFooter.jsx';
import { useAmenitySettingsForm } from '../hooks/useAmenitySettingsForm.js';
import { useAmenitiesStore } from '../store/useAmenitiesStore.js';

export default function AmenitySettingsPage() {
  const { amenity } = useOutletContext();
  const isSaving = useAmenitiesStore((state) => state.isSavingSettings);
  const settingsError = useAmenitiesStore((state) => state.settingsError);
  const saveAmenitySettings = useAmenitiesStore(
    (state) => state.saveAmenitySettings
  );
  const clearSettingsError = useAmenitiesStore(
    (state) => state.clearSettingsError
  );
  const form = useAmenitySettingsForm(amenity, (settings) =>
    saveAmenitySettings(amenity.id, settings)
  );

  useEffect(() => {
    clearSettingsError();
  }, [amenity.id, clearSettingsError]);

  return (
    <form onSubmit={form.submitSettings} className="space-y-5">
      <GeneralSettingsCard
        values={form.values}
        errors={form.errors}
        onChange={form.updateField}
      />
      <BookingSettingsCard
        values={form.values}
        onChange={form.updateField}
      />
      <PaymentSettingsCard
        values={form.values}
        errors={form.errors}
        onChange={form.updateField}
      />
      <AvailabilitySettingsCard
        values={form.values}
        errors={form.errors}
        onChange={form.updateField}
        onToggleDay={form.toggleDay}
      />
      <MaintenanceSettingsCard
        values={form.values}
        errors={form.errors}
        onChange={form.updateField}
      />
      <SettingsFooter
        isDirty={form.isDirty}
        isSaving={isSaving}
        error={settingsError}
        onReset={() => {
          clearSettingsError();
          form.resetChanges();
        }}
      />
    </form>
  );
}
