import { todayISO } from '../../lib/dates';

// New residents get an unpaid invoice seeded by acceptRequest (in the pending
// slice) — that write targets this collection through the shared store.
export const createPaymentsSlice = (set, get) => ({
  payments: [],

  payInvoice: (invoiceId, paymentMethod) => {
    const p = get().payments.find((pay) => pay.id === invoiceId);
    set((s) => ({
      payments: s.payments.map((x) =>
        x.id === invoiceId ? { ...x, status: 'Paid', paidOn: todayISO(), paymentMethod } : x
      ),
    }));
    get().showToast(`Payment of ₹${p ? p.amount : ''} Successful!`, 'success');
    get().addActivity(`Paid maintenance bill for ${p ? p.title : 'dues'}`, 'payment');
  },
});
