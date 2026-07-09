import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { Settings, Shield, Bell, CreditCard, Save } from 'lucide-react';

export default function SettingsPage() {
  const { showToast } = useApp();
  const [autoBilling, setAutoBilling] = useState(true);
  const [fineCharge, setFineCharge] = useState(true);
  const [gateSecurity, setGateSecurity] = useState(true);
  const [noticeAlert, setNoticeAlert] = useState(false);

  const handleSave = () => {
    showToast('Admin Settings Saved Successfully', 'success');
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
          {/* Automated Billing */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <CreditCard className="w-4 h-4 text-indigo-500" />
                Automated Monthly Maintenance
              </p>
              <p className="text-slate-400 font-semibold max-w-md">
                Automatically generate and email maintenance fee invoices of ₹4,250 on the 1st of every calendar month.
              </p>
            </div>
            <button
              onClick={() => setAutoBilling(!autoBilling)}
              className={`w-11 h-6 rounded-full transition-colors flex items-center p-0.5 relative ${
                autoBilling ? 'bg-indigo-600' : 'bg-slate-200'
              }`}
            >
              <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                autoBilling ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </div>

          {/* Late Payment Fines */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <CreditCard className="w-4 h-4 text-indigo-500" />
                Late Payment Fine Charges
              </p>
              <p className="text-slate-400 font-semibold max-w-md">
                Charge a flat ₹100 weekly fine on invoices that remain unpaid after 10 days of the specified due date.
              </p>
            </div>
            <button
              onClick={() => setFineCharge(!fineCharge)}
              className={`w-11 h-6 rounded-full transition-colors flex items-center p-0.5 relative ${
                fineCharge ? 'bg-indigo-600' : 'bg-slate-200'
              }`}
            >
              <span className={`w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
                fineCharge ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </div>

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
            className="bg-indigo-600 hover:bg-indigo-755 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 flex items-center gap-1.5"
          >
            <Save className="w-4 h-4" />
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
