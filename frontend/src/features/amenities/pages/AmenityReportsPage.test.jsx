import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AmenityReportsPage from './AmenityReportsPage.jsx';

// The summary tiles, against `GET /amenity-reports`.
//
// Four of them — Total Amenities, Pending Approvals, Active Amenities,
// Bookings This Month — named figures `amenity_report_totals` does not compute,
// so the response never carried them and each rendered a hardcoded `0` beside
// the real numbers, indistinguishable from a measurement of nothing (issue #48
// D4). The six that remain are 1:1 with the RPC, and the response's own
// `options.bookingStatuses` drives the status filter, so the page invents no
// status vocabulary of its own.

const mocks = vi.hoisted(() => ({ report: vi.fn() }));

vi.mock('../amenitiesApi.js', () => ({
  amenitiesApi: { report: mocks.report },
}));

const KPIS = {
  totalBookings: 42,
  totalActiveBookings: 31,
  cancelledBookings: 7,
  totalCharged: 88000,
  totalRevenue: 61000,
  totalRefunded: 9000,
};

const response = (overrides = {}) => ({
  rows: [],
  kpis: KPIS,
  options: {
    amenities: [{ value: 'a1', label: 'Clubhouse' }],
    // Sent by the server exactly as it is; the page renders the list it is
    // given rather than a list of its own.
    bookingStatuses: ['pending', 'approved', 'cancelled', 'rejected'],
  },
  ...overrides,
});

beforeEach(() => {
  mocks.report.mockReset().mockResolvedValue(response());
});

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AmenityReportsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
};

const summary = async () =>
  screen.findByRole('region', { name: 'Amenity report summary' });

describe('amenity report KPIs', () => {
  it('shows the six figures the report actually computes', async () => {
    renderPage();
    const cards = await summary();

    expect(within(cards).getByText('Total Bookings')).toBeInTheDocument();
    expect(within(cards).getByText('42')).toBeInTheDocument();

    expect(within(cards).getByText('Approved Bookings')).toBeInTheDocument();
    expect(within(cards).getByText('31')).toBeInTheDocument();

    expect(within(cards).getByText('Cancelled Bookings')).toBeInTheDocument();
    expect(within(cards).getByText('7')).toBeInTheDocument();

    expect(within(cards).getByText('Total Charged')).toBeInTheDocument();
    expect(within(cards).getByText('₹88,000')).toBeInTheDocument();

    expect(within(cards).getByText('Total Revenue')).toBeInTheDocument();
    expect(within(cards).getByText('₹61,000')).toBeInTheDocument();

    expect(within(cards).getByText('Total Refunded')).toBeInTheDocument();
    expect(within(cards).getByText('₹9,000')).toBeInTheDocument();
  });

  it('draws exactly six tiles — no card without a source figure', async () => {
    renderPage();
    const cards = await summary();

    expect(within(cards).getAllByRole('article')).toHaveLength(6);
  });

  it('no longer renders the four KPIs the RPC cannot answer', async () => {
    renderPage();
    await summary();

    ['Total Amenities', 'Pending Approvals', 'Active Amenities', 'Bookings This Month'].forEach(
      (deadLabel) => {
        expect(screen.queryByText(deadLabel)).not.toBeInTheDocument();
      }
    );
  });

  it('falls back to zeros only when the response carries no kpis at all', async () => {
    mocks.report.mockResolvedValue(response({ kpis: undefined }));
    renderPage();
    const cards = await summary();

    expect(within(cards).getAllByText('0')).toHaveLength(3);
    expect(within(cards).getAllByText('₹0')).toHaveLength(3);
  });
});

describe('amenity report status filter', () => {
  it('offers the statuses the response sent, labelled for a reader', async () => {
    renderPage();
    await summary();

    const statusFilter = screen.getByLabelText('Booking Status');
    const optionLabels = within(statusFilter)
      .getAllByRole('option')
      .map((option) => option.textContent);

    expect(optionLabels).toEqual([
      'All',
      'Pending Approval',
      'Approved',
      'Cancelled',
      'Rejected',
    ]);
  });

  it('labels a lowercase machine status the wire may add later', async () => {
    mocks.report.mockResolvedValue(
      response({
        options: {
          amenities: [],
          bookingStatuses: ['completed', 'no_show'],
        },
      })
    );
    renderPage();
    await summary();

    const statusFilter = screen.getByLabelText('Booking Status');
    expect(
      within(statusFilter).getByRole('option', { name: 'No Show' })
    ).toBeInTheDocument();
    expect(
      within(statusFilter).queryByRole('option', { name: 'no_show' })
    ).not.toBeInTheDocument();
  });
});
