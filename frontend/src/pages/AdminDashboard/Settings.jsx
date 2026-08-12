import React, { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useApp } from '../../store/useApp';
import { Settings, Shield, Bell, CreditCard, Save } from 'lucide-react';
import { api } from '../../lib/api/client';
import LocationCoordinatesInput from '../../components/common/LocationCoordinatesInput';
import { moneyApi } from '../../features/money/moneyApi';

const numberFieldClass = 'w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold';

// Reads and writes `GET`/`PUT /billing-settings` directly rather than the
// billing fields `GET /settings` also echoes: that copy is read-only (`settings.py`'s
// module docstring says so explicitly -- "readable here and writable only at
// PUT /billing-settings") and carries none of the amounts, prefixes or grace
// periods this screen also needs to show. Two switches, and the numbers each
// one needs beside it: the database refuses turning a switch on without its
// number (409), so the fields live together rather than the toggle floating
// free of what it configures.
const DEFAULT_BILLING_FORM = {
  currency: 'INR',
  invoiceNumberPrefix: 'INV',
  defaultMaintenanceAmount: '',
  maintenanceDueDay: 15,
  defaultTaxPercent: 0,
  autoBillingEnabled: false,
  autoBillingDay: 1,
  lateFeeEnabled: false,
  lateFeeAmount: '',
  lateFeeGraceDays: 10,
  lateFeePeriod: 'weekly',
};

function billingFormFromSettings(settings) {
  if (!settings) return DEFAULT_BILLING_FORM;
  return {
    currency: settings.currency ?? 'INR',
    invoiceNumberPrefix: settings.invoiceNumberPrefix ?? 'INV',
    defaultMaintenanceAmount: settings.defaultMaintenanceAmount ?? '',
    maintenanceDueDay: settings.maintenanceDueDay ?? 15,
    defaultTaxPercent: settings.defaultTaxPercent ?? 0,
    autoBillingEnabled: settings.autoBillingEnabled ?? false,
    autoBillingDay: settings.autoBillingDay ?? 1,
    lateFeeEnabled: settings.lateFeeEnabled ?? false,
    lateFeeAmount: settings.lateFeeAmount ?? '',
    lateFeeGraceDays: settings.lateFeeGraceDays ?? 10,
    lateFeePeriod: settings.lateFeePeriod ?? 'weekly',
  };
}

export default function SettingsPage() {
  const { showToast } = useApp();
  const queryClient = useQueryClient();
  const [gateSecurity, setGateSecurity] = useState(false);
  const [noticeAlert, setNoticeAlert] = useState(false);
  const [coordinates, setCoordinates] = useState({ latitude: '', longitude: '' });
  const [billingForm, setBillingForm] = useState(DEFAULT_BILLING_FORM);

  useEffect(() => {
    async function loadSettings() {
      try {
        const data = await api('/settings');
        setNoticeAlert(data.preferences?.noticeSmsBroadcastEnabled ?? false);
        setGateSecurity(data.preferences?.requireVisitorPreapproval ?? false);
        setCoordinates({
          latitude: data.community?.latitude ?? '',
          longitude: data.community?.longitude ?? '',
        });
      } catch {
        showToast('Failed to load current settings', 'error');
      }
    }
    loadSettings();
  }, [showToast]);

  const billingSettings = useQuery({
    queryKey: ['billing-settings'],
    queryFn: moneyApi.getBillingSettings,
  });

  useEffect(() => {
    if (billingSettings.data) setBillingForm(billingFormFromSettings(billingSettings.data));
  }, [billingSettings.data]);

  const updateBilling = useMutation({
    mutationFn: (payload) => moneyApi.updateBillingSettings(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['billing-settings'], updated);
    },
  });

  const setBillingField = (field) => (value) => setBillingForm((form) => ({ ...form, [field]: value }));

  const handleSave = async () => {
    if (coordinates.latitude === '' || coordinates.longitude === '') {
      showToast('Community coordinates are required', 'error');
      return;
    }
    // The range check has to live here. `LocationCoordinatesInput` marks its
    // two inputs `required` with `min`/`max`, but this page saves from a button
    // rather than a form submit, and native constraint validation only runs on
    // submit -- so on this screen alone those attributes never fire. Without
    // this, a latitude of 999 reached `PUT /settings`, failed Pydantic's
    // `le=90`, and came back as an unexplained 422 toast naming no field.
    const latitude = Number(coordinates.latitude);
    const longitude = Number(coordinates.longitude);
    if (
      !Number.isFinite(latitude) || latitude < -90 || latitude > 90
      || !Number.isFinite(longitude) || longitude < -180 || longitude > 180
    ) {
      showToast('Latitude must be between -90 and 90, and longitude between -180 and 180', 'error');
      return;
    }
    // The same class of round trip the coordinate check avoids: the database
    // refuses a switch turned on without the number it needs, but catching it
    // here means a blank amount reads as "fill this in" instead of a 409 toast
    // naming a field the admin cannot see from a closed toggle.
    if (billingForm.autoBillingEnabled && !(Number(billingForm.defaultMaintenanceAmount) > 0)) {
      showToast('Set a maintenance amount above zero before enabling automated billing', 'error');
      return;
    }
    if (billingForm.lateFeeEnabled && !(Number(billingForm.lateFeeAmount) > 0)) {
      showToast('Set a late fee amount above zero before enabling late fee charges', 'error');
      return;
    }
    try {
      await Promise.all([
        api('/settings', {
          method: 'PUT',
          body: JSON.stringify({
            requireVisitorPreapproval: gateSecurity,
            noticeSmsBroadcastEnabled: noticeAlert,
            latitude,
            longitude,
          })
        }),
        updateBilling.mutateAsync({
          currency: billingForm.currency,
          invoiceNumberPrefix: billingForm.invoiceNumberPrefix,
          defaultMaintenanceAmount: billingForm.defaultMaintenanceAmount === '' ? null : Number(billingForm.defaultMaintenanceAmount),
          maintenanceDueDay: Number(billingForm.maintenanceDueDay),
          defaultTaxPercent: Number(billingForm.defaultTaxPercent),
          autoBillingEnabled: billingForm.autoBillingEnabled,
          autoBillingDay: Number(billingForm.autoBillingDay),
          lateFeeEnabled: billingForm.lateFeeEnabled,
          lateFeeAmount: billingForm.lateFeeAmount === '' ? null : Number(billingForm.lateFeeAmount),
          lateFeeGraceDays: Number(billingForm.lateFeeGraceDays),
          lateFeePeriod: billingForm.lateFeePeriod,
        }),
      ]);
      showToast('Admin Settings Saved Successfully', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to save settings', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Society Settings</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Configure global parameters, security rule triggers, and automated maintenance collections.</p>
      </div>

      <div className="max-w-2xl bg-white border border-slate-100 rounded-3xl p-6 shadow-sm space-y-6">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-50">
          <Settings className="w-5 h-5 text-indigo-650" />
          <h3 className="font-extrabold text-slate-805 text-sm">Global Configurations</h3>
        </div>

        <div className="space-y-6 text-xs font-semibold text-slate-600">
          <LocationCoordinatesInput value={coordinates} onChange={setCoordinates} idPrefix="community-settings" required />

          {billingSettings.isLoading ? (
            <p className="text-slate-400 font-semibold">Loading billing settings…</p>
          ) : billingSettings.error ? (
            <p role="alert" className="text-rose-600 font-semibold">
              {billingSettings.error.message || 'Could not load billing settings.'}
            </p>
          ) : (
            <>
              {/* Automated Billing */}
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                      <CreditCard className="w-4 h-4 text-indigo-500" />
                      Automated Monthly Maintenance
                    </p>
                    <p className="text-slate-400 font-semibold max-w-md">
                      Reserve a default maintenance amount that new invoices bill against.
                      Nothing runs on a schedule yet -- this configures the rate, not a job.
                    </p>
                  </div>
                  <button
                    onClick={() => setBillingField('autoBillingEnabled')(!billingForm.autoBillingEnabled)}
                    className={`w-11 h-6 rounded-full transition-colors flex items-center p-0.5 relative shrink-0 ${
                      billingForm.autoBillingEnabled ? 'bg-indigo-600' : 'bg-slate-200'
                    }`}
                  >
                    <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                      billingForm.autoBillingEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`} />
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3 pl-5.5">
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Maintenance amount (₹)</span>
                    <input
                      type="number" min="0" step="1"
                      value={billingForm.defaultMaintenanceAmount}
                      onChange={(e) => setBillingField('defaultMaintenanceAmount')(e.target.value)}
                      className={numberFieldClass}
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Runs on day</span>
                    <input
                      type="number" min="1" max="28"
                      value={billingForm.autoBillingDay}
                      onChange={(e) => setBillingField('autoBillingDay')(e.target.value)}
                      className={numberFieldClass}
                    />
                  </label>
                </div>
              </div>

              {/* Late Payment Fines */}
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                      <CreditCard className="w-4 h-4 text-indigo-500" />
                      Late Payment Fine Charges
                    </p>
                    <p className="text-slate-400 font-semibold max-w-md">
                      Reserve the flat fine and grace period invoices left unpaid past their
                      due date would be charged. Nothing charges it automatically yet.
                    </p>
                  </div>
                  <button
                    onClick={() => setBillingField('lateFeeEnabled')(!billingForm.lateFeeEnabled)}
                    className={`w-11 h-6 rounded-full transition-colors flex items-center p-0.5 relative shrink-0 ${
                      billingForm.lateFeeEnabled ? 'bg-indigo-600' : 'bg-slate-200'
                    }`}
                  >
                    <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                      billingForm.lateFeeEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`} />
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-3 pl-5.5">
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Fine amount (₹)</span>
                    <input
                      type="number" min="0" step="1"
                      value={billingForm.lateFeeAmount}
                      onChange={(e) => setBillingField('lateFeeAmount')(e.target.value)}
                      className={numberFieldClass}
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Grace days</span>
                    <input
                      type="number" min="0" max="90"
                      value={billingForm.lateFeeGraceDays}
                      onChange={(e) => setBillingField('lateFeeGraceDays')(e.target.value)}
                      className={numberFieldClass}
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Charged</span>
                    <select
                      value={billingForm.lateFeePeriod}
                      onChange={(e) => setBillingField('lateFeePeriod')(e.target.value)}
                      className={numberFieldClass}
                    >
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                      <option value="once">One-time</option>
                    </select>
                  </label>
                </div>
              </div>

              {/* General billing configuration */}
              <div className="space-y-2">
                <p className="text-sm font-bold text-slate-800">Billing configuration</p>
                <div className="grid grid-cols-3 gap-3">
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Currency</span>
                    <input
                      maxLength={3}
                      value={billingForm.currency}
                      onChange={(e) => setBillingField('currency')(e.target.value.toUpperCase())}
                      className={numberFieldClass}
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Invoice prefix</span>
                    <input
                      maxLength={12}
                      value={billingForm.invoiceNumberPrefix}
                      onChange={(e) => setBillingField('invoiceNumberPrefix')(e.target.value.toUpperCase())}
                      className={numberFieldClass}
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Due day</span>
                    <input
                      type="number" min="1" max="28"
                      value={billingForm.maintenanceDueDay}
                      onChange={(e) => setBillingField('maintenanceDueDay')(e.target.value)}
                      className={numberFieldClass}
                    />
                  </label>
                </div>
                <label className="space-y-1 block max-w-[10rem]">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Default tax %</span>
                  <input
                    type="number" min="0" max="99.99" step="0.01"
                    value={billingForm.defaultTaxPercent}
                    onChange={(e) => setBillingField('defaultTaxPercent')(e.target.value)}
                    className={numberFieldClass}
                  />
                </label>
              </div>
            </>
          )}

          {/* Gate Security pre-approvals */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-indigo-500" />
                Gate Security App Pre-approvals
              </p>
              <p className="text-slate-400 font-semibold max-w-md">
                Mandate all delivery and service visitors to generate passcodes. Unapproved gate entries will trigger gatekeeper call alerts.
              </p>
            </div>
            <button
              onClick={() => setGateSecurity(!gateSecurity)}
              className={`w-11 h-6 rounded-full transition-colors flex items-center p-0.5 relative ${
                gateSecurity ? 'bg-indigo-600' : 'bg-slate-200'
              }`}
            >
              <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                gateSecurity ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </div>

          {/* Notice alerts */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <Bell className="w-4 h-4 text-indigo-500" />
                Urgent Notice SMS Broadcast
              </p>
              <p className="text-slate-400 font-semibold max-w-md">
                Send direct cellular SMS broadcasts to all registered mobile phones when a High Priority Notice is posted.
              </p>
            </div>
            <button
              onClick={() => setNoticeAlert(!noticeAlert)}
              className={`w-11 h-6 rounded-full transition-colors flex items-center p-0.5 relative ${
                noticeAlert ? 'bg-indigo-600' : 'bg-slate-200'
              }`}
            >
              <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                noticeAlert ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-50 flex justify-end">
          <button
            onClick={handleSave}
            disabled={billingSettings.isLoading || updateBilling.isPending}
            className="bg-indigo-600 hover:bg-indigo-755 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 flex items-center gap-1.5 disabled:opacity-60"
          >
            <Save className="w-4 h-4" />
            {updateBilling.isPending ? 'Saving…' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}
