import { describe, expect, it } from 'vitest';
import { getLedgerMenuActions } from './amenityLedger';

// The only part of the ledger wiring worth a test. Everything else on that
// screen is react-query around six thin wrappers, and a mock for those would be
// a test of the mock.
//
// What can be got wrong here is money. `availableActions` is the server's
// answer and must pass through untouched — narrowing it would hide a refund
// somebody is owed, and widening it would draw a button the API refuses. The
// two the client adds are the ones the API gates by arithmetic instead of by a
// flag, so this is where the arithmetic is checked.

const transaction = (overrides = {}) => ({
  availableActions: ['view'],
  paymentStatus: 'pending',
  totalAmount: 1000,
  amountPaid: 1000,
  outstandingDeposit: 0,
  ...overrides,
});

describe('getLedgerMenuActions', () => {
  it("passes the server's own actions through in order", () => {
    const actions = getLedgerMenuActions(
      transaction({ availableActions: ['view', 'refund', 'damage'] })
    );
    expect(actions.slice(0, 3)).toEqual(['view', 'refund', 'damage']);
  });

  it('offers a payment while the deposit is short', () => {
    expect(getLedgerMenuActions(transaction({ outstandingDeposit: 500 }))).toContain(
      'payment'
    );
  });

  it('offers a payment while charges are unpaid', () => {
    expect(
      getLedgerMenuActions(transaction({ totalAmount: 1100, amountPaid: 800 }))
    ).toContain('payment');
  });

  it('withholds a payment when nothing is owed, because the API would refuse it', () => {
    expect(getLedgerMenuActions(transaction())).not.toContain('payment');
  });

  it('always offers a charge on an open booking — billing after the fact is the point', () => {
    expect(getLedgerMenuActions(transaction())).toContain('charge');
    expect(
      getLedgerMenuActions(transaction({ paymentStatus: 'paid' }))
    ).toContain('charge');
  });

  it('adds nothing to a refunded or cancelled row', () => {
    // Financially closed. A new charge here would strand the ledger in
    // `partially_paid` against a booking nobody is going to settle.
    expect(
      getLedgerMenuActions(
        transaction({ paymentStatus: 'refunded', outstandingDeposit: 500 })
      )
    ).toEqual(['view']);
    expect(
      getLedgerMenuActions(
        transaction({ paymentStatus: 'cancelled', totalAmount: 900, amountPaid: 0 })
      )
    ).toEqual(['view']);
  });

  it('survives a row that arrived without availableActions', () => {
    const { availableActions: _unused, ...rest } = transaction();
    expect(getLedgerMenuActions(rest)).toEqual(['charge']);
  });
});
