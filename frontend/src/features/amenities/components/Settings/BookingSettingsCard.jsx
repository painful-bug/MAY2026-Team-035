import React from 'react';
import { CalendarCheck } from 'lucide-react';
import SettingsCard from './SettingsCard.jsx';
import ToggleField from './ToggleField.jsx';

const BOOKING_TOGGLES = [
  {
    field: 'requireAdminApproval',
    label: 'Require Admin Approval',
    description: 'New resident requests enter the approval queue.',
  },
  {
    field: 'allowPrivateBooking',
    label: 'Allow Private Booking',
    description: 'Residents may reserve the amenity exclusively.',
  },
  {
    field: 'allowRecurringBooking',
    label: 'Allow Recurring Booking',
    description: 'Recurring schedules can be offered in a future workflow.',
  },
  {
    field: 'allowGuestBooking',
    label: 'Allow Guest Booking',
    description: 'Bookings may include guest information.',
  },
  {
    field: 'allowSameDayBooking',
    label: 'Allow Same-Day Booking',
    description: 'Residents may request a slot on the current day.',
  },
  {
    field: 'enableWaitlist',
    label: 'Enable Waitlist',
    description: 'Retain demand when a time slot is unavailable.',
  },
  {
    field: 'enableAutoApproval',
    label: 'Enable Auto Approval',
    description: 'Eligible resident requests can bypass manual review.',
  },
];

export default function BookingSettingsCard({ values, onChange }) {
  return (
    <SettingsCard
      icon={CalendarCheck}
      title="Booking Settings"
      description="Configure the rules applied to resident booking requests."
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {BOOKING_TOGGLES.map((option) => (
          <ToggleField
            key={option.field}
            {...option}
            checked={values[option.field]}
            onChange={(checked) => onChange(option.field, checked)}
          />
        ))}
      </div>
    </SettingsCard>
  );
}
