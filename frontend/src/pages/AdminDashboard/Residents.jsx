import { useState } from 'react';
import { Check, Copy, Link2, Loader2, UserPlus } from 'lucide-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { registrationApi } from '../../features/registration/registrationApi';

const initialForm = { full_name: '', invitee_email: '', phone: '', intended_unit_id: '' };

export default function Residents() {
  const [form, setForm] = useState(initialForm);
  const [invite, setInvite] = useState(null);
  const [copied, setCopied] = useState('');
  const units = useQuery({ queryKey: ['admin-units'], queryFn: registrationApi.adminUnits });
  const create = useMutation({
    mutationFn: registrationApi.createInvitation,
    onSuccess: (result) => { setInvite(result); setForm(initialForm); },
  });

  const submit = (event) => {
    event.preventDefault();
    create.mutate({
      full_name: form.full_name.trim() || null,
      invitee_email: form.invitee_email.trim(),
      phone: form.phone.trim() || null,
      intended_unit_id: form.intended_unit_id,
    });
  };
  const copy = async (field, value) => {
    await navigator.clipboard?.writeText(value);
    setCopied(field);
    window.setTimeout(() => setCopied(''), 1500);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Invite a resident</h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">Create an email-bound registration invitation. The link and code are shown only once.</p>
      </div>
      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Full name (optional)<input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} className="block w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700" /></label>
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Verified email<input required type="email" value={form.invitee_email} onChange={(event) => setForm({ ...form, invitee_email: event.target.value })} className="block w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700" /></label>
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Phone (optional)<input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="+919812345678" className="block w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-700" /></label>
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Unit<select required value={form.intended_unit_id} onChange={(event) => setForm({ ...form, intended_unit_id: event.target.value })} className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700"><option value="">{units.isLoading ? 'Loading units…' : 'Select a unit'}</option>{units.data?.items?.map((unit) => <option key={unit.id} value={unit.id}>{unit.building_name ? `${unit.building_name} · ` : ''}{unit.unit_code}</option>)}</select></label>
        </div>
        {units.error || create.error ? <p role="alert" className="text-sm font-semibold text-rose-600">{(units.error || create.error).message}</p> : null}
        <button type="submit" disabled={create.isPending || units.isLoading} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white disabled:opacity-60">{create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}Create invitation</button>
      </form>
      {invite ? (
        <section className="space-y-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-6">
          <div><h2 className="font-extrabold text-emerald-900">Invitation created</h2><p className="mt-1 text-sm font-medium text-emerald-800">Share this with {invite.invitee_email}. It expires {new Date(invite.expires_at).toLocaleString()} and will not be shown again after you leave this page.</p></div>
          <CopyField label="Registration link" value={invite.link} copied={copied === 'link'} onCopy={() => copy('link', invite.link)} />
          <CopyField label="Registration code" value={invite.code} copied={copied === 'code'} onCopy={() => copy('code', invite.code)} />
        </section>
      ) : null}
    </div>
  );
}

function CopyField({ label, value, copied, onCopy }) {
  return <label className="block text-xs font-bold uppercase tracking-wider text-emerald-800">{label}<span className="mt-2 flex items-center gap-2 rounded-xl border border-emerald-200 bg-white p-2"><code className="min-w-0 flex-1 truncate text-sm normal-case text-slate-700">{value}</code><button type="button" onClick={onCopy} className="rounded-lg p-2 text-emerald-700 hover:bg-emerald-50" aria-label={`Copy ${label}`}>{copied ? <Check className="h-4 w-4" /> : label.includes('link') ? <Link2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button></span></label>;
}
