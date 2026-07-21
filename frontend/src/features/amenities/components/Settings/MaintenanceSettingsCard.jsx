import React from 'react';
import { Wrench } from 'lucide-react';
import { MAINTENANCE_INTERVAL_OPTIONS } from '../../constants/amenitySettings.js';
import AmenityFormField, { amenityInputClasses } from '../AmenityFormField.jsx';
import NumberField from './NumberField.jsx';
import SettingsCard from './SettingsCard.jsx';
import ToggleField from './ToggleField.jsx';

export default function MaintenanceSettingsCard({ values, errors, onChange }) {
  return (
    <SettingsCard
      icon={Wrench}
      title="Maintenance Settings"
      description="Configure maintenance defaults for future scheduling workflows."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <AmenityFormField label="Maintenance Interval">
          <select
            value={values.maintenanceInterval}
            onChange={(event) =>
              onChange('maintenanceInterval', event.target.value)
            }
            className={amenityInputClasses}
          >
            {MAINTENANCE_INTERVAL_OPTIONS.map((interval) => (
              <option key={interval} value={interval}>
                {interval}
              </option>
            ))}
          </select>
        </AmenityFormField>
        <NumberField
          label="Default Maintenance Duration (min)"
          required
          min={1}
          value={values.defaultMaintenanceDurationMinutes}
          error={errors.defaultMaintenanceDurationMinutes}
          onChange={(value) =>
            onChange('defaultMaintenanceDurationMinutes', value)
          }
        />
        <div className="sm:col-span-2">
          <ToggleField
            label="Auto Block Maintenance Slots"
            description="Automatically reserve configured maintenance periods when scheduling is introduced."
            checked={values.autoBlockMaintenanceSlots}
            onChange={(checked) =>
              onChange('autoBlockMaintenanceSlots', checked)
            }
          />
        </div>
        <div className="sm:col-span-2">
          <AmenityFormField label="Maintenance Notes">
            <textarea
              rows={3}
              value={values.maintenanceNotes}
              onChange={(event) =>
                onChange('maintenanceNotes', event.target.value)
              }
              placeholder="Add recurring maintenance instructions."
              className={`${amenityInputClasses} resize-none`}
            />
          </AmenityFormField>
        </div>
      </div>
    </SettingsCard>
  );
}
