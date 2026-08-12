export const formatLedgerCurrency = (amount) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(amount || 0));

export const formatLedgerDate = (date) =>
  new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

/**
 * What the row's actions menu should offer.
 *
 * `transaction.availableActions` comes from the server and is authoritative for
 * the four it covers — view, refund, damage and force-cancel — because it is
 * computed from the same rules the write endpoints enforce. It is passed
 * through untouched and never second-guessed here.
 *
 * Two more are appended, because the API gates them by arithmetic the row
 * already carries rather than by a flag:
 *
 *   payment — `POST .../payments` refuses money against a charge that is
 *     already settled (`409`, "no outstanding charge of that kind"). So it is
 *     offered only while something is outstanding: the deposit, or the booking
 *     and additional charges taken together. A cancelled or refunded row is
 *     financially closed and is not offered it, whatever the sums say.
 *
 *   charge — `POST .../charges` has no precondition; its only failure is a
 *     booking that does not exist. Billing after the fact is the whole point of
 *     it, so a completed booking is exactly when it is wanted. Only a fully
 *     closed row is excluded, where a new charge nobody can pay would strand
 *     the ledger in `partially_paid` for ever.
 *
 * Pure, and separate from the component, so the rule can be read and tested
 * without a DOM.
 */
export const getLedgerMenuActions = (transaction) => {
  const serverActions = Array.isArray(transaction.availableActions)
    ? transaction.availableActions
    : [];
  const isClosed = ['refunded', 'cancelled'].includes(transaction.paymentStatus);

  if (isClosed) {
    return serverActions;
  }

  const owesDeposit = Number(transaction.outstandingDeposit || 0) > 0;
  const owesCharges =
    Number(transaction.totalAmount || 0) - Number(transaction.amountPaid || 0) > 0;
  const extra = [];

  if (owesDeposit || owesCharges) {
    extra.push('payment');
  }
  extra.push('charge');

  return [...serverActions, ...extra];
};
