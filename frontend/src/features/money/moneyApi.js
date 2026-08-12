import { api } from '../../lib/api/client';

// Billing settings, invoices and admin-recorded payments.
//
// Same shape as `features/hiring/hiringApi.js` and
// `features/departments/departmentsApi.js`: no state, no caching, no error
// translation. react-query owns all three.
//
// **`recordPayment` marks money as already received.** It is the admin's
// bookkeeping entry for a payment taken outside the app (cash, a bank
// transfer confirmed by phone) -- never a checkout, and never reachable from
// a resident screen. See `backend/app/api/v1/routers/money.py`'s module
// docstring for why the resident `payInvoice` action must stay unwired.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });
const put = (path, body = {}) => api(path, { method: 'PUT', body: JSON.stringify(body) });

export const moneyApi = {
  // --- billing configuration --------------------------------------------------
  /** The community's billing configuration -- rates, prefixes, the two switches. */
  getBillingSettings: () => api('/billing-settings'),
  /**
   * Patch the billing configuration. Omitted fields are left unchanged.
   *
   * Sending `defaultMaintenanceAmount: null` (or `lateFeeAmount: null`) clears
   * the rate; omitting the key leaves it as it was. The database refuses
   * `autoBillingEnabled: true` / `lateFeeEnabled: true` without the amount each
   * needs, as a `409` -- there is no client-side guess at that rule here, only
   * a message surfaced from the one the server enforces.
   */
  updateBillingSettings: (payload) => put('/billing-settings', payload),

  // --- invoices and payments --------------------------------------------------
  /**
   * Issue one invoice against one flat. `unitId` or `flat` identifies the unit;
   * `flat` (`B-1204`) creates it on first reference.
   */
  createInvoice: (payload) => post('/invoices', payload),
  /**
   * Record money already received against an invoice, and return the invoice
   * as it now stands. Idempotent on `reference`: the same reference sent twice
   * returns the payment already recorded rather than crediting the invoice
   * again.
   */
  recordPayment: (invoiceId, payload) => post(`/invoices/${invoiceId}/payments`, payload),
};
