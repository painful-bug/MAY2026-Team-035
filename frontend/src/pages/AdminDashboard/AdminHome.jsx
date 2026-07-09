import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import {
  AlertOctagon,
  AlertTriangle,
  BellRing,
  Building2,
  ClipboardList,
  Eye,
  Home,
  Plus,
  RotateCcw,
  Trash2,
  UserPlus,
  Users,
  X,
} from 'lucide-react';

const emptyRegistrationForm = {
  address: '',
  members: [
    { name: '', phone: '' },
    { name: '', phone: '' },
  ],
};

export default function AdminHome() {
  const { users } = useApp();
  const [addResidentOpen, setAddResidentOpen] = useState(false);
  const residentsCount = users.filter((u) => u.role === 'Resident').length;

  const complaintStatus = [
    { label: 'Open', value: 7, color: 'bg-rose-500' },
    { label: 'In Progress', value: 4, color: 'bg-amber-500' },
    { label: 'Resolved', value: 26, color: 'bg-emerald-600' },
  ];

  const quickActions = [
    {
      label: 'Add New Resident',
      icon: UserPlus,
      onClick: () => setAddResidentOpen(true),
    },
    {
      label: 'Complaints',
      icon: AlertOctagon,
    },
    {
      label: 'Create Department',
      icon: ClipboardList,
    },
    {
      label: 'Publish Notice',
      icon: BellRing,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Admin Dashboard</h1>
          <p className="text-xs font-semibold text-slate-400">
            Header, society stats, complaint status, and quick actions.
          </p>
        </div>

        <div className="grid w-full max-w-md grid-cols-2 rounded-full border border-slate-200 bg-white p-1 text-xs font-bold shadow-sm">
          <button className="rounded-full bg-indigo-600 px-4 py-2.5 text-white shadow-md shadow-indigo-100">
            Admin View
          </button>
          <button className="rounded-full px-4 py-2.5 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-800">
            Resident View
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="space-y-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">Welcome, Anita Desai</h2>
                  <p className="text-xs font-semibold text-slate-400">Sunrise Housing Society</p>
                </div>
              </div>
              <p className="max-w-md text-xs font-semibold leading-relaxed text-slate-400">
                Tapping Resident View switches to the admin's own personal dashboard for dues, visitors, and resident activity.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard
              icon={Users}
              label="Registered Residents"
              value={residentsCount}
              caption="Total resident profiles"
            />
            <StatCard
              icon={UserPlus}
              label="Visitors Today"
              value="18"
              caption="Expected and checked-in"
            />
            <div className="rounded-2xl border border-slate-100 bg-white p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                  Complaints Status
                </span>
                <AlertOctagon className="h-4 w-4 text-rose-600" />
              </div>
              <div className="space-y-3">
                {complaintStatus.map((item) => (
                  <div key={item.label} className="flex items-center justify-between gap-3 text-xs font-bold text-slate-700">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${item.color}`} />
                      <span>{item.label}</span>
                    </div>
                    <span className="text-slate-900">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <section className="space-y-3">
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
              Quick Actions
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {quickActions.map((action) => (
                <QuickActionButton key={action.label} action={action} />
              ))}
            </div>
          </section>

          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-center">
            <p className="text-xs font-semibold text-slate-400">
              More modules soon: billing, gate management, staff routing, and reports.
            </p>
          </div>
        </div>
      </div>

      {addResidentOpen && <AddResidentModal onClose={() => setAddResidentOpen(false)} />}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, caption }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-3xl font-extrabold text-slate-900">{value}</p>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">{label}</p>
            <p className="mt-1 text-[11px] font-semibold text-slate-400">{caption}</p>
          </div>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function QuickActionButton({ action }) {
  return (
    <button
      type="button"
      onClick={action.onClick}
      className="group flex min-h-28 flex-col items-start justify-between rounded-2xl border border-slate-100 bg-white p-5 text-left transition-all hover:border-slate-200 hover:bg-slate-50"
    >
      <ActionIcon icon={action.icon} />
      <span className="text-sm font-extrabold text-slate-800">{action.label}</span>
    </button>
  );
}

function ActionIcon({ icon: Icon }) {
  return (
    <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-700 transition-colors group-hover:border-indigo-100 group-hover:bg-white group-hover:text-indigo-600">
      <Icon className="h-4 w-4" />
    </span>
  );
}

function AddResidentModal({ onClose }) {
  const { getResidentsAtResidence, registerResidenceMembers } = useApp();
  const [form, setForm] = useState(emptyRegistrationForm);
  const [step, setStep] = useState('form');
  const [conflictResidents, setConflictResidents] = useState([]);

  const validMembers = form.members
    .map((member) => ({ name: member.name.trim(), phone: member.phone.trim() }))
    .filter((member) => member.name && member.phone);
  const inlineConflict =
    form.address.trim() && getResidentsAtResidence(form.address).length > 0;

  const resetForm = () => {
    setForm(emptyRegistrationForm);
    setConflictResidents([]);
    setStep('form');
  };

  const updateMember = (index, field, value) => {
    setForm((current) => ({
      ...current,
      members: current.members.map((member, memberIndex) =>
        memberIndex === index ? { ...member, [field]: value } : member
      ),
    }));
  };

  const addMemberRow = () => {
    setForm((current) => ({
      ...current,
      members: [...current.members, { name: '', phone: '' }],
    }));
  };

  const removeMemberRow = (index) => {
    setForm((current) => ({
      ...current,
      members: current.members.filter((_, memberIndex) => memberIndex !== index),
    }));
  };

  const commitRegistration = (replaceExisting) => {
    const result = registerResidenceMembers({
      address: form.address,
      members: form.members,
      replaceExisting,
    });
    if (result.ok) {
      onClose();
    }
  };

  const submitForm = (event) => {
    event.preventDefault();
    if (!form.address.trim() || validMembers.length === 0) return;

    const residentsAtAddress = getResidentsAtResidence(form.address);
    if (residentsAtAddress.length > 0) {
      setConflictResidents(residentsAtAddress);
      setStep('conflict');
      return;
    }

    commitRegistration(false);
  };

  let body = null;
  if (step === 'conflict') {
    body = (
      <AddressConflictWarning
        address={form.address}
        onViewResidents={() => setStep('residents')}
        onProceed={() => commitRegistration(true)}
      />
    );
  } else if (step === 'residents') {
    body = (
      <CurrentResidentsView
        address={form.address}
        residents={conflictResidents}
        onBack={() => setStep('conflict')}
        onContinue={() => commitRegistration(true)}
      />
    );
  } else {
    body = (
      <ResidenceRegistrationForm
        form={form}
        inlineConflict={inlineConflict}
        onSubmit={submitForm}
        onReset={resetForm}
        onAddressChange={(address) => setForm((current) => ({ ...current, address }))}
        onMemberChange={updateMember}
        onAddMember={addMemberRow}
        onRemoveMember={removeMemberRow}
      />
    );
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-xl space-y-6 rounded-3xl border border-slate-100 bg-white p-6 shadow-xl shadow-slate-100 animate-slide-up max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-5 top-5 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-700"
          aria-label="Close registration popup"
        >
          <X className="h-5 w-5" />
        </button>
        {body}
      </div>
    </div>
  );
}

function ResidenceRegistrationForm({
  form,
  inlineConflict,
  onSubmit,
  onReset,
  onAddressChange,
  onMemberChange,
  onAddMember,
  onRemoveMember,
}) {
  return (
    <>
      <ModalHeader
        icon={Home}
        title="Add New Residence & Members"
        subtitle="Register all members currently living at one residence."
      />

      <form onSubmit={onSubmit} className="space-y-5">
        <Field label="Residence Address">
          <input
            value={form.address}
            onChange={(event) => onAddressChange(event.target.value)}
            placeholder="12 Cedar Lane, Block B"
            className={inputClass}
          />
          {inlineConflict && (
            <p className="mt-1.5 flex items-center gap-1.5 text-[11px] font-bold text-rose-600">
              <AlertTriangle className="h-3.5 w-3.5" />
              Address in use - will overwrite existing residents after confirmation
            </p>
          )}
        </Field>

        <div className="flex min-h-24 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-center">
          <div className="space-y-1">
            <Building2 className="mx-auto h-5 w-5 text-slate-300" />
            <p className="text-[11px] font-bold text-slate-400">Optional mini-map placeholder</p>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            Members
          </p>
          {form.members.map((member, index) => (
            <div key={index} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <input
                value={member.name}
                onChange={(event) => onMemberChange(index, 'name', event.target.value)}
                placeholder="Full name"
                className={inputClass}
              />
              <input
                value={member.phone}
                onChange={(event) => onMemberChange(index, 'phone', event.target.value)}
                placeholder="Phone number"
                className={inputClass}
              />
              <button
                type="button"
                onClick={() => onRemoveMember(index)}
                disabled={form.members.length === 1}
                className="flex h-10 w-full items-center justify-center rounded-xl border border-slate-100 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-40 sm:w-10"
                aria-label="Remove member"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={onAddMember}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-slate-200 px-4 py-3 text-xs font-bold text-indigo-600 transition-colors hover:border-indigo-200 hover:bg-indigo-50"
          >
            <Plus className="h-4 w-4" />
            Add another member
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-1">
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-100 px-4 py-3 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50"
          >
            <RotateCcw className="h-4 w-4" />
            Refresh Form
          </button>
          <button
            type="submit"
            className="rounded-xl bg-indigo-600 px-4 py-3 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
          >
            Register
          </button>
        </div>

        <p className="text-[11px] font-semibold text-slate-400">
          Conflict check runs when Register is selected. Existing members are only replaced after confirmation.
        </p>
      </form>
    </>
  );
}

function AddressConflictWarning({ address, onViewResidents, onProceed }) {
  return (
    <>
      <ModalHeader
        icon={AlertTriangle}
        title="Warning: Address Occupied"
        titleClassName="text-rose-700"
        subtitle="This residence already has registered members."
      />

      <div className="space-y-4">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
          <p className="text-sm font-semibold leading-relaxed text-slate-700">
            Registering new members to <span className="font-extrabold text-slate-900">{address}</span> will permanently remove the current residents.
          </p>
        </div>
        <button
          type="button"
          onClick={onViewResidents}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm font-bold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <Eye className="h-4 w-4" />
          View & Remove Current Members
        </button>
        <button
          type="button"
          onClick={onProceed}
          className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white shadow-md shadow-slate-200 transition-colors hover:bg-slate-800"
        >
          Proceed Anyway
        </button>
        <p className="text-[11px] font-semibold text-slate-400">
          This warning only appears when the selected address is occupied in the dummy resident data.
        </p>
      </div>
    </>
  );
}

function CurrentResidentsView({ address, residents, onBack, onContinue }) {
  return (
    <>
      <ModalHeader
        icon={Users}
        title={`Current Residents at ${address}`}
        subtitle="Read-only list for confirming who will be replaced."
      />

      <div className="space-y-4">
        <div className="divide-y divide-slate-100 rounded-2xl border border-slate-100">
          {residents.map((resident) => (
            <div key={resident.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <span className="text-sm font-bold text-slate-800">{resident.name}</span>
              <span className="text-xs font-semibold text-slate-400">{resident.phone}</span>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={onBack}
            className="rounded-xl border border-slate-200 px-4 py-3 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50"
          >
            Go Back
          </button>
          <button
            type="button"
            onClick={onContinue}
            className="rounded-xl bg-rose-600 px-4 py-3 text-xs font-bold text-white shadow-md shadow-rose-100 transition-colors hover:bg-rose-700"
          >
            Remove & Continue
          </button>
        </div>
      </div>
    </>
  );
}

function ModalHeader({ icon: Icon, title, subtitle, titleClassName = 'text-slate-900' }) {
  return (
    <div className="flex items-start gap-3 pr-10">
      <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <h3 className={`text-lg font-extrabold tracking-tight ${titleClassName}`}>{title}</h3>
        <p className="mt-1 text-xs font-semibold text-slate-400">{subtitle}</p>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-700 transition-all placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none';
