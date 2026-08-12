import { Link } from 'react-router-dom';
import { AlertTriangle, Phone } from 'lucide-react';
import { PageHeading } from '../../features/security/components/Primitives';

// **The society's own numbers are deliberately absent.** The demo screen this
// replaces listed a "Society Management Office" line that was invented — no
// endpoint in this API returns a community contact number, so any number
// rendered here would be one somebody made up, and a made-up number on an
// emergency screen is worse than no screen. The three below are India's real
// national emergency lines and need no backend.
//
// When community settings grow a contacts field, this is where it goes.

const NUMBERS = [
  ['112', 'Emergency response', 'Police, fire or ambulance — the single national number.'],
  ['101', 'Fire brigade', 'Direct line, if you already know it is a fire.'],
  ['108', 'Ambulance', 'Medical emergencies and accidents.'],
];

export default function Emergency() {
  return (
    <div className="space-y-6">
      <PageHeading
        title="Emergency"
        description="Call first. File the incident once the people who are coming have been called."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {NUMBERS.map(([number, label, detail]) => (
          <a
            key={number}
            href={`tel:${number}`}
            className="rounded-2xl border border-rose-100 bg-white p-5 shadow-sm hover:border-rose-300"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-rose-50 p-2.5 text-rose-600">
                <Phone className="h-5 w-5" />
              </div>
              <p className="text-3xl font-extrabold tracking-tight text-slate-900">{number}</p>
            </div>
            <p className="mt-3 text-xs font-bold text-slate-800">{label}</p>
            <p className="mt-1 text-[11px] font-semibold text-slate-400">{detail}</p>
          </a>
        ))}
      </div>

      <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-amber-50 p-2.5 text-amber-600">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-extrabold text-slate-900">Then record it</h2>
            <p className="mt-1 text-xs font-semibold text-slate-500">
              An incident filed as <strong>high</strong> or <strong>critical</strong> notifies
              every admin and manager in the community the moment you save it. That is the
              fastest way to reach the committee from the gate.
            </p>
            <Link
              to="../incidents"
              className="mt-4 inline-flex rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
            >
              File an incident
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
