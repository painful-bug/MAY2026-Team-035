import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import CommunitySearch from './CommunitySearch';

describe('CommunitySearch', () => {
  it('shares search submission and result rendering across onboarding flows', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const onSubmit = vi.fn();
    render(
      <CommunitySearch
        label="Find your community"
        value="Green"
        onChange={onChange}
        onSubmit={onSubmit}
        submitLabel="Search"
        items={[{ id: 'one', name: 'Green Meadows' }]}
        renderResult={(row) => <p key={row.id}>{row.name}</p>}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(screen.getByText('Green Meadows')).toBeVisible();
  });

  it('renders loading, error, and empty states accessibly', () => {
    const { rerender } = render(
      <CommunitySearch value="" onChange={() => {}} isLoading renderResult={() => null} />,
    );
    expect(screen.getByText('Searching communities…')).toBeVisible();

    rerender(<CommunitySearch value="" onChange={() => {}} error="Search failed" renderResult={() => null} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Search failed');

    rerender(<CommunitySearch value="" onChange={() => {}} showEmpty emptyMessage="Nothing nearby" renderResult={() => null} />);
    expect(screen.getByText('Nothing nearby')).toBeVisible();
  });
});
