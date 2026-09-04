import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { CalendarClock, CloudOff, DoorOpen, RefreshCw, Wifi, X } from 'lucide-react';
import { securityApi } from '../../features/security/securityApi';
import { useOfflineGate } from '../../features/security/offline/useOfflineGate';
import QrScanner from '../../features/security/components/QrScanner';
import VerdictCard from '../../features/security/components/VerdictCard';
import {
  Empty,
  ErrorText,
  Loading,
  PageHeading,
  Pill,
} from '../../features/security/components/Primitives';
import { shortDateTime } from '../../features/security/components/vocabulary';

// The barrier. One action — scan — and one answer.
//
// There is no separate check-out control anywhere on this screen, because
// `0040` makes the second scan the way out: presenting the same credential
// again checks the visitor out. A guard at a barrier does one thing, and the
// gesture is the same in both directions.
//
// **The offline path is not a degraded mode bolted on the side; it is the same
// control taking a different route.** The guard scans the same way whether or
// not there is a network — what changes is where the answer comes from and
// whether the card says the answer is provisional. See
// `features/security/offline/offlineGate.js` for why that is safe.
//
// The expected-visitors panel is the offline bundle read online. That endpoint
// exists to be cached for an outage, but it is also the only forward view of
// visitors a guard has — `/visitor-passes` is resident-facing and returns only
// the caller's own passes. Reusing it here costs one request and no new
// endpoint.

export default function GateHome() {
  const [verdict, setVerdict] = useState(null);
  const [provisional, setProvisional] = useState(false);
  const gate = useOfflineGate();

  const verify = useMutation({
    mutationFn: async (credential) => {
      if (gate.online) {
        try {
          const result = await securityApi.verify({ credential });
          return { result, provisional: false };
        } catch {
          // Preserve the existing cached verification path on connection failure.
        }
      }
      const result = await gate.verifyOffline(credential);
      return { result, provisional: true };
    },
    // Repeating verification can check a visitor out, so never retry it automatically.
    retry: false,
    onSuccess: ({ result, provisional }) => {
      setVerdict(result);
      setProvisional(provisional);
    },
  });

  // A provisional card must not outlive the sync that settled it. Without this
  // the guard is still reading "the server has not seen it yet" underneath a
  // banner saying the server just refused it — two contradictory sentences on
  // one screen, and the stale one is the reassuring one.
  useEffect(() => {
    if (gate.outcome && provisional) {
      setVerdict(null);
      setProvisional(false);
    }
  }, [gate.outcome, provisional]);

  const expected = gate.bundle?.passes || [];

  return (
    <div className="space-y-6">
      <PageHeading
        title="Gate"
        description="Scan a visitor pass to admit or check out. A second scan of the same pass is the way out."
        action={<ConnectionChip gate={gate} />}
      />

      {!gate.online ? <OfflineBanner gate={gate} /> : null}
      {gate.pending.length > 0 && gate.online ? <PendingBanner gate={gate} /> : null}
      {gate.outcome ? <OutcomeBanner gate={gate} /> : null}
      <ErrorText error={gate.syncError} />
      <RejectedList gate={gate} />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <QrScanner
            onScan={verify.mutateAsync}
            busy={verify.isPending}
            hint={
              gate.online
                ? 'Scan the resident QR, or enter its six-digit security code.'
                : 'Offline — checked against the cached pass list on this device.'
            }
          />
          <VerdictCard
            verdict={verdict}
            provisional={provisional}
            onDismiss={() => setVerdict(null)}
          />
        </div>

        <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-amber-50 p-2.5 text-amber-600">
              <CalendarClock className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-slate-900">Expected visitors</h2>
              <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
                Passes valid at this gate over the next twelve hours.
              </p>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {gate.bundleQuery.isPending && !gate.bundle ? <Loading /> : null}
            <ErrorText error={gate.bundleQuery.error} />
            {!gate.bundleQuery.isPending && expected.length === 0 ? (
              <Empty>Nobody is expected in the next twelve hours.</Empty>
            ) : null}

            {expected.map((pass) => (
              <article
                key={pass.passId}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-800">{pass.visitorName}</p>
                  <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
                    {pass.unitCode || 'Flat not recorded'}
                    {pass.guestCount > 1 ? ` · ${pass.guestCount} guests` : ''}
                  </p>
                </div>
                <div className="shrink-0 text-right text-[10px] font-bold text-slate-400">
                  <p>{shortDateTime(pass.validFrom)}</p>
                  <p className="mt-0.5 font-semibold">to {shortDateTime(pass.validUntil)}</p>
                </div>
              </article>
            ))}
          </div>

          <p className="mt-5 flex items-start gap-2 text-[11px] font-semibold text-slate-400">
            <DoorOpen className="mt-px h-4 w-4 shrink-0" />
            This list holds no codes — only hashes reach a gate device. Verify by scanning.
          </p>
        </section>
      </div>
    </div>
  );
}

function ConnectionChip({ gate }) {
  return (
    <div className="flex items-center gap-2">
      <Pill
        className={
          gate.online ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'
        }
      >
        {gate.online ? (
          <span className="inline-flex items-center gap-1.5">
            <Wifi className="h-3.5 w-3.5" /> Online
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <CloudOff className="h-3.5 w-3.5" /> Offline
          </span>
        )}
      </Pill>
      {gate.pending.length > 0 ? (
        <Pill className="bg-indigo-100 text-indigo-700">{gate.pending.length} to sync</Pill>
      ) : null}
    </div>
  );
}

function OfflineBanner({ gate }) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
      <p className="flex items-start gap-2 text-xs font-bold text-amber-900">
        <CloudOff className="mt-px h-4 w-4 shrink-0" />
        {gate.bundleUsable
          ? 'The gate is offline. Scans are checked against the pass list cached on this device and recorded for confirmation when the connection returns.'
          : 'The gate is offline and the cached pass list has expired, so codes cannot be checked here. Record entries in the registers and verify them once the connection returns.'}
      </p>
      {gate.bundleFetchedAt ? (
        <p className="mt-2 text-[11px] font-semibold text-amber-800">
          Pass list cached {shortDateTime(gate.bundleFetchedAt)}, valid until{' '}
          {shortDateTime(gate.bundle?.expiresAt)}.
        </p>
      ) : null}
    </div>
  );
}

function PendingBanner({ gate }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-indigo-100 bg-indigo-50 p-4">
      <p className="text-xs font-bold text-indigo-900">
        {gate.pending.length} offline{' '}
        {gate.pending.length === 1 ? 'entry has' : 'entries have'} not been confirmed by the
        server yet.
      </p>
      <button
        type="button"
        onClick={() => void gate.sync()}
        disabled={gate.syncing}
        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white disabled:opacity-60"
      >
        <RefreshCw className={`h-4 w-4 ${gate.syncing ? 'animate-spin' : ''}`} />
        {gate.syncing ? 'Syncing…' : 'Sync now'}
      </button>
    </div>
  );
}

function OutcomeBanner({ gate }) {
  const { accepted, rejected, replayed } = gate.outcome;
  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
      <p className="text-xs font-bold text-emerald-900">
        Sync finished: {accepted} confirmed, {replayed} already recorded, {rejected} refused by
        the server.
      </p>
      <button
        type="button"
        onClick={gate.clearOutcome}
        aria-label="Dismiss"
        className="rounded-full bg-white/70 p-1.5 text-emerald-800"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

/**
 * The entries the server refused.
 *
 * These are the point of the whole mechanism: somebody the guard admitted that
 * the server says should not have been. They stay until dismissed one by one,
 * because clearing them in a batch is the same as not showing them.
 */
function RejectedList({ gate }) {
  if (gate.rejected.length === 0) return null;
  return (
    <div className="space-y-2">
      {gate.rejected.map((entry) => (
        <div
          key={entry.sourceClientId}
          className="flex items-start justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4"
        >
          <div>
            <p className="text-xs font-extrabold text-rose-900">
              Server refused an offline entry — {entry.serverVerdict}
            </p>
            <p className="mt-1 text-[11px] font-semibold text-rose-800">
              {entry.serverDetail || 'The server did not accept this admission.'}
            </p>
            {/* "scanned", not "admitted" — the claimed verdict may itself have
                been a refusal, and telling a guard they admitted somebody they
                turned away is the kind of wrong that costs trust in the panel. */}
            <p className="mt-1 text-[11px] font-semibold text-rose-700">
              {entry.visitorName ? `${entry.visitorName} · ` : ''}
              scanned here at {shortDateTime(entry.presentedAt)}, decided offline as{' '}
              {entry.claimedVerdict}
            </p>
          </div>
          <button
            type="button"
            onClick={() => gate.dismiss(entry.sourceClientId)}
            aria-label="Dismiss"
            className="rounded-full bg-white/70 p-1.5 text-rose-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
