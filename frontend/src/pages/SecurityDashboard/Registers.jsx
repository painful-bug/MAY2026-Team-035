import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { securityApi } from '../../features/security/securityApi';
import ExportButton from '../../features/security/components/ExportButton';
import {
  Empty,
  ErrorText,
  GateModal,
  Loading,
  PageHeading,
  Pill,
  TabBar,
} from '../../features/security/components/Primitives';
import {
  DIRECTION_STYLES,
  DIRECTIONS,
  inputClass,
  labelClass,
  shortDateTime,
} from '../../features/security/components/vocabulary';

// The two registers `US-3.3` and `US-3.4` describe, on one screen with a tab —
// they are the same act (write down what came through the gate) with different
// columns, and a guard switches between them a dozen times a shift.
//
// **Every write carries a `sourceClientId` minted when the form opens, not when
// it is submitted.** That is what makes a retry safe: the id is unique per
// community, so a second attempt after a dropped connection returns the row the
// first one wrote instead of writing a duplicate. Minting per attempt would
// defeat it exactly when it matters.

const TABS = [
  ['materials', 'Materials'],
  ['tankers', 'Water tankers'],
];

export default function Registers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab = TABS.some(([id]) => id === tabParam) ? tabParam : 'materials';
  const setTab = (next) =>
    setSearchParams(
      (params) => {
        const copy = new URLSearchParams(params);
        copy.set('tab', next);
        return copy;
      },
      { replace: true }
    );

  const [range, setRange] = useState({ from: '', to: '' });

  return (
    <div className="space-y-6">
      <PageHeading
        title="Gate registers"
        description="What came in, what went out, and which tankers are on site."
      />

      <div className="flex flex-wrap items-end gap-3">
        <TabBar tabs={TABS} active={tab} onChange={setTab} />
        <div className="flex gap-2">
          <div>
            <label className={labelClass} htmlFor="range-from">
              From
            </label>
            <input
              id="range-from"
              type="date"
              value={range.from}
              onChange={(event) =>
                setRange((current) => ({ ...current, from: event.target.value }))
              }
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="range-to">
              To
            </label>
            <input
              id="range-to"
              type="date"
              value={range.to}
              onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))}
              className={`${inputClass} mt-1`}
            />
          </div>
        </div>
      </div>

      {tab === 'materials' ? <Materials range={range} /> : <Tankers range={range} />}
    </div>
  );
}

/** A date input gives `YYYY-MM-DD`; the API wants an instant. */
function asRange({ from, to }) {
  return {
    from: from ? new Date(`${from}T00:00:00`).toISOString() : undefined,
    to: to ? new Date(`${to}T23:59:59`).toISOString() : undefined,
  };
}

// --------------------------------------------------------------------------
// Materials — US-3.3
// --------------------------------------------------------------------------

function Materials({ range }) {
  const queryClient = useQueryClient();
  const [outstandingOnly, setOutstandingOnly] = useState(false);
  const [recording, setRecording] = useState(false);

  const filters = {
    ...asRange(range),
    outstanding: outstandingOnly ? true : undefined,
  };
  const movements = useQuery({
    queryKey: ['security', 'movements', filters],
    queryFn: () => securityApi.movements(filters),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['security', 'movements'] });

  const record = useMutation({
    mutationFn: (payload) => securityApi.recordMovement(payload),
    onSuccess: () => {
      setRecording(false);
      invalidate();
    },
  });

  const markReturned = useMutation({
    mutationFn: (movementId) => securityApi.returnMovement(movementId),
    onSuccess: invalidate,
  });

  const rows = movements.data || [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex items-center gap-2 text-xs font-bold text-slate-600">
          <input
            type="checkbox"
            checked={outstandingOnly}
            onChange={(event) => setOutstandingOnly(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          Outstanding only
        </label>
        <ExportButton dataset="material-movements" {...asRange(range)} />
        <button
          type="button"
          onClick={() => setRecording(true)}
          className="ml-auto inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
        >
          <Plus className="h-4 w-4" />
          Record a movement
        </button>
      </div>

      <ErrorText error={movements.error} />
      <ErrorText error={markReturned.error} />
      {movements.isPending ? <Loading /> : null}
      {!movements.isPending && !movements.error && rows.length === 0 ? (
        <Empty>Nothing recorded in this range.</Empty>
      ) : null}

      <div className="space-y-3">
        {rows.map((movement) => (
          <article
            key={movement.id}
            className={`rounded-2xl border bg-white p-5 shadow-sm ${
              movement.isOverdue ? 'border-rose-200' : 'border-slate-100'
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill className={DIRECTION_STYLES[movement.direction]}>
                    {movement.direction}
                  </Pill>
                  {movement.isReturnable ? (
                    <Pill
                      className={
                        movement.isOverdue
                          ? 'bg-rose-100 text-rose-700'
                          : movement.isOutstanding
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-emerald-100 text-emerald-700'
                      }
                    >
                      {movement.isOverdue
                        ? 'Overdue'
                        : movement.isOutstanding
                          ? 'Out'
                          : 'Returned'}
                    </Pill>
                  ) : null}
                </div>
                <p className="mt-2 text-sm font-bold text-slate-900">{movement.description}</p>
                <p className="mt-1 text-[11px] font-semibold text-slate-400">
                  {movement.quantity ? `${movement.quantity} ${movement.unit || ''} · ` : ''}
                  {shortDateTime(movement.recordedAt)}
                  {movement.carrierName ? ` · ${movement.carrierName}` : ''}
                  {movement.vehicleNumber ? ` · ${movement.vehicleNumber}` : ''}
                  {movement.unitCode ? ` · ${movement.unitCode}` : ''}
                  {movement.postName ? ` · ${movement.postName}` : ''}
                </p>
                {movement.isReturnable && movement.expectedReturnAt ? (
                  <p className="mt-1 text-[11px] font-semibold text-slate-400">
                    Expected back {shortDateTime(movement.expectedReturnAt)}
                  </p>
                ) : null}
              </div>

              {movement.isReturnable && movement.isOutstanding ? (
                <button
                  type="button"
                  disabled={markReturned.isPending}
                  onClick={() => markReturned.mutate(movement.id)}
                  className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                >
                  Mark returned
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      {recording ? (
        <MovementForm
          onClose={() => setRecording(false)}
          onSubmit={(payload) => record.mutate(payload)}
          pending={record.isPending}
          error={record.error}
        />
      ) : null}
    </section>
  );
}

function MovementForm({ onClose, onSubmit, pending, error }) {
  // Minted once, when the form opens — see the module header.
  const sourceClientId = useMemo(() => crypto.randomUUID(), []);
  const [form, setForm] = useState({
    direction: 'inward',
    description: '',
    quantity: '',
    unit: '',
    isReturnable: false,
    expectedReturnAt: '',
    carrierName: '',
    vehicleNumber: '',
    notes: '',
  });
  const set = (key) => (event) =>
    setForm((current) => ({
      ...current,
      [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
    }));

  return (
    <GateModal
      title="Record a movement"
      description="Anything carried through the gate, in either direction."
      onClose={onClose}
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({
            sourceClientId,
            direction: form.direction,
            description: form.description.trim(),
            quantity: form.quantity ? Number(form.quantity) : undefined,
            unit: form.unit.trim() || undefined,
            isReturnable: form.isReturnable,
            expectedReturnAt:
              form.isReturnable && form.expectedReturnAt
                ? new Date(form.expectedReturnAt).toISOString()
                : undefined,
            carrierName: form.carrierName.trim() || undefined,
            vehicleNumber: form.vehicleNumber.trim() || undefined,
            notes: form.notes.trim() || undefined,
          });
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="movement-direction">
              Direction
            </label>
            <select
              id="movement-direction"
              value={form.direction}
              onChange={set('direction')}
              className={`${inputClass} mt-1`}
            >
              {DIRECTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass} htmlFor="movement-vehicle">
              Vehicle
            </label>
            <input
              id="movement-vehicle"
              maxLength={40}
              value={form.vehicleNumber}
              onChange={set('vehicleNumber')}
              placeholder="KL07AB1234"
              className={`${inputClass} mt-1`}
            />
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="movement-description">
            What
          </label>
          <input
            id="movement-description"
            required
            maxLength={500}
            value={form.description}
            onChange={set('description')}
            placeholder="12 bags of cement"
            className={`${inputClass} mt-1`}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className={labelClass} htmlFor="movement-quantity">
              Quantity
            </label>
            <input
              id="movement-quantity"
              type="number"
              min="0"
              step="any"
              value={form.quantity}
              onChange={set('quantity')}
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="movement-unit">
              Unit
            </label>
            <input
              id="movement-unit"
              maxLength={40}
              value={form.unit}
              onChange={set('unit')}
              placeholder="bags"
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="movement-carrier">
              Carried by
            </label>
            <input
              id="movement-carrier"
              maxLength={120}
              value={form.carrierName}
              onChange={set('carrierName')}
              className={`${inputClass} mt-1`}
            />
          </div>
        </div>

        <label className="flex items-center gap-2 text-xs font-bold text-slate-600">
          <input
            type="checkbox"
            checked={form.isReturnable}
            onChange={set('isReturnable')}
            className="h-4 w-4 rounded border-slate-300"
          />
          This is expected back
        </label>

        {form.isReturnable ? (
          <div>
            <label className={labelClass} htmlFor="movement-expected">
              Expected back
            </label>
            <input
              id="movement-expected"
              type="datetime-local"
              value={form.expectedReturnAt}
              onChange={set('expectedReturnAt')}
              className={`${inputClass} mt-1`}
            />
          </div>
        ) : null}

        <div>
          <label className={labelClass} htmlFor="movement-notes">
            Notes
          </label>
          <textarea
            id="movement-notes"
            rows={3}
            maxLength={500}
            value={form.notes}
            onChange={set('notes')}
            className={`${inputClass} mt-1`}
          />
        </div>

        <ErrorText error={error} />

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending}
            className="flex-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
          >
            {pending ? 'Recording…' : 'Record'}
          </button>
        </div>
      </form>
    </GateModal>
  );
}

// --------------------------------------------------------------------------
// Tankers — US-3.4
// --------------------------------------------------------------------------

function Tankers({ range }) {
  const queryClient = useQueryClient();
  const [onSiteOnly, setOnSiteOnly] = useState(false);
  const [recording, setRecording] = useState(false);

  const filters = { ...asRange(range), onSite: onSiteOnly ? true : undefined };
  const tankers = useQuery({
    queryKey: ['security', 'tankers', filters],
    queryFn: () => securityApi.tankers(filters),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['security', 'tankers'] });

  const record = useMutation({
    mutationFn: (payload) => securityApi.recordTanker(payload),
    onSuccess: () => {
      setRecording(false);
      invalidate();
    },
  });

  const markDeparted = useMutation({
    mutationFn: (logId) =>
      securityApi.updateTanker(logId, { departedAt: new Date().toISOString() }),
    onSuccess: invalidate,
  });

  const rows = tankers.data || [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex items-center gap-2 text-xs font-bold text-slate-600">
          <input
            type="checkbox"
            checked={onSiteOnly}
            onChange={(event) => setOnSiteOnly(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          On site only
        </label>
        <ExportButton dataset="water-tankers" {...asRange(range)} />
        <button
          type="button"
          onClick={() => setRecording(true)}
          className="ml-auto inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
        >
          <Plus className="h-4 w-4" />
          Log a tanker
        </button>
      </div>

      <ErrorText error={tankers.error} />
      <ErrorText error={markDeparted.error} />
      {tankers.isPending ? <Loading /> : null}
      {!tankers.isPending && !tankers.error && rows.length === 0 ? (
        <Empty>No tankers logged in this range.</Empty>
      ) : null}

      <div className="space-y-3">
        {rows.map((tanker) => (
          <article
            key={tanker.id}
            className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill
                    className={
                      tanker.isOnSite
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-slate-100 text-slate-600'
                    }
                  >
                    {tanker.isOnSite ? 'On site' : 'Departed'}
                  </Pill>
                  <span className="font-mono text-xs font-extrabold text-slate-800">
                    {tanker.tankerNumber}
                  </span>
                </div>
                <p className="mt-2 text-[11px] font-semibold text-slate-400">
                  {tanker.supplierName ? `${tanker.supplierName} · ` : ''}
                  {tanker.volumeLitres ? `${tanker.volumeLitres} L · ` : ''}
                  Arrived {shortDateTime(tanker.arrivedAt)}
                  {tanker.departedAt ? ` · left ${shortDateTime(tanker.departedAt)}` : ''}
                </p>
                {tanker.driverName ? (
                  <p className="mt-1 text-[11px] font-semibold text-slate-400">
                    {tanker.driverName}
                    {tanker.driverPhoneE164 ? ` · ${tanker.driverPhoneE164}` : ''}
                  </p>
                ) : null}
              </div>

              {tanker.isOnSite ? (
                <button
                  type="button"
                  disabled={markDeparted.isPending}
                  onClick={() => markDeparted.mutate(tanker.id)}
                  className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                >
                  Record departure
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      {recording ? (
        <TankerForm
          onClose={() => setRecording(false)}
          onSubmit={(payload) => record.mutate(payload)}
          pending={record.isPending}
          error={record.error}
        />
      ) : null}
    </section>
  );
}

function TankerForm({ onClose, onSubmit, pending, error }) {
  const sourceClientId = useMemo(() => crypto.randomUUID(), []);
  const [form, setForm] = useState({
    tankerNumber: '',
    supplierName: '',
    volumeLitres: '',
    driverName: '',
    driverPhoneE164: '',
    notes: '',
  });
  const set = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <GateModal
      title="Log a water tanker"
      description="Record the departure later — the number is stored upper-cased so one plate stays one vehicle."
      onClose={onClose}
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({
            sourceClientId,
            tankerNumber: form.tankerNumber.trim(),
            supplierName: form.supplierName.trim() || undefined,
            volumeLitres: form.volumeLitres ? Number(form.volumeLitres) : undefined,
            driverName: form.driverName.trim() || undefined,
            driverPhoneE164: form.driverPhoneE164.trim() || undefined,
            notes: form.notes.trim() || undefined,
          });
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="tanker-number">
              Tanker number
            </label>
            <input
              id="tanker-number"
              required
              maxLength={40}
              value={form.tankerNumber}
              onChange={set('tankerNumber')}
              placeholder="KL07AB1234"
              className={`${inputClass} mt-1 font-mono`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="tanker-supplier">
              Supplier
            </label>
            <input
              id="tanker-supplier"
              maxLength={120}
              value={form.supplierName}
              onChange={set('supplierName')}
              className={`${inputClass} mt-1`}
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className={labelClass} htmlFor="tanker-volume">
              Litres
            </label>
            <input
              id="tanker-volume"
              type="number"
              min="1"
              value={form.volumeLitres}
              onChange={set('volumeLitres')}
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="tanker-driver">
              Driver
            </label>
            <input
              id="tanker-driver"
              maxLength={120}
              value={form.driverName}
              onChange={set('driverName')}
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="tanker-phone">
              Driver phone
            </label>
            <input
              id="tanker-phone"
              maxLength={20}
              value={form.driverPhoneE164}
              onChange={set('driverPhoneE164')}
              placeholder="+919876543210"
              className={`${inputClass} mt-1`}
            />
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="tanker-notes">
            Notes
          </label>
          <textarea
            id="tanker-notes"
            rows={3}
            maxLength={500}
            value={form.notes}
            onChange={set('notes')}
            className={`${inputClass} mt-1`}
          />
        </div>

        <ErrorText error={error} />

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending}
            className="flex-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
          >
            {pending ? 'Logging…' : 'Log tanker'}
          </button>
        </div>
      </form>
    </GateModal>
  );
}
