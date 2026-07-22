const AMENITY_LEDGER_STORAGE_KEY = 'homebandhu-amenity-ledger';
const AMENITY_LEDGER_VERSION_KEY = 'homebandhu-amenity-ledger-version';
const AMENITY_LEDGER_VERSION = '2';

let memoryFallback = null;

const cloneTransactions = (transactions) =>
  transactions.map((transaction) => ({
    ...transaction,
    refundHistory: (transaction.refundHistory ?? []).map((entry) => ({
      ...entry,
    })),
    damageHistory: (transaction.damageHistory ?? []).map((entry) => ({
      ...entry,
    })),
    cancellationHistory: (transaction.cancellationHistory ?? []).map(
      (entry) => ({ ...entry })
    ),
    auditTrail: (transaction.auditTrail ?? []).map((entry) => ({
      ...entry,
    })),
  }));

const isValidLedger = (transactions) =>
  Array.isArray(transactions) &&
  transactions.every(
    (transaction) =>
      transaction &&
      typeof transaction.id === 'string' &&
      typeof transaction.bookingId === 'string' &&
      typeof transaction.paymentStatus === 'string'
  );

const getLocalStorage = () => {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.localStorage;
};

const persistTransactions = (transactions) => {
  const records = cloneTransactions(transactions);
  const storage = getLocalStorage();

  if (storage) {
    storage.setItem(AMENITY_LEDGER_STORAGE_KEY, JSON.stringify(records));
    storage.setItem(AMENITY_LEDGER_VERSION_KEY, AMENITY_LEDGER_VERSION);
  } else {
    memoryFallback = records;
  }

  return cloneTransactions(records);
};

export const loadAmenityLedger = (initialTransactions) => {
  const storage = getLocalStorage();

  if (!storage) {
    if (memoryFallback === null) {
      memoryFallback = cloneTransactions(initialTransactions);
    }

    return cloneTransactions(memoryFallback);
  }

  const persistedValue = storage.getItem(AMENITY_LEDGER_STORAGE_KEY);

  if (persistedValue === null) {
    return persistTransactions(initialTransactions);
  }

  try {
    let transactions = JSON.parse(persistedValue);

    if (!isValidLedger(transactions)) {
      throw new TypeError('Persisted amenity ledger is invalid.');
    }

    if (
      storage.getItem(AMENITY_LEDGER_VERSION_KEY) !== AMENITY_LEDGER_VERSION
    ) {
      const seedById = new Map(
        initialTransactions.map((transaction) => [transaction.id, transaction])
      );
      transactions = transactions.map((transaction) => {
        const seed = seedById.get(transaction.id);

        return seed
          ? {
              ...seed,
              ...transaction,
              bookingId: seed.bookingId,
              bookingDate: seed.bookingDate,
              bookingStatus: seed.bookingStatus,
            }
          : transaction;
      });
      return persistTransactions(transactions);
    }

    return cloneTransactions(transactions);
  } catch {
    return persistTransactions(initialTransactions);
  }
};

export const saveAmenityLedger = (transactions) =>
  persistTransactions(transactions);
