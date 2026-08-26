import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { departmentsApi } from '../departmentsApi';
import { QUERY_POLICIES } from '../../../lib/api/queryClient';
import TokenCombobox from './TokenCombobox';

// The category field, replacing a hardcoded six-item checkbox grid.
//
// **Categories are names, not ids, on the department wire.** `POST /departments`
// takes `categories: string[]` and `upsert_category_names` creates any it has
// not seen in that community — which is why there is no "create category"
// endpoint and no create call here. Choosing a new name and saving the form IS
// creating it. The combobox's add row therefore only puts the name in the
// chip list; the write happens with the department.
//
// That also means the id on each chip is local bookkeeping. A category that
// already exists carries its real id, and a newly typed one carries its own
// name as the id — enough for React keys and for de-duplication, and never sent
// anywhere.
//
// WHAT THIS FIELD SHOWS THAT NOTHING SHOWED BEFORE
//
// `skillName` is null when a category's name matches no trade in the
// catalogue. That has been legal since the link was built, and its consequence
// — the category matches no service person in any hiring search, so complaints
// filed under it reach nobody — was invisible. Here it is an amber line under
// the name.

export default function CategoryPicker({ selected, onChange, required = false }) {
  const [query, setQuery] = useState('');

  const categories = useQuery({
    queryKey: ['complaint-categories'],
    queryFn: departmentsApi.categories,
    ...QUERY_POLICIES.reference,
  });

  const all = useMemo(() => categories.data || [], [categories.data]);
  const typed = query.trim().toLowerCase();

  const rows = useMemo(
    () =>
      all
        .filter((row) => !typed || row.name.toLowerCase().includes(typed))
        .slice(0, 8)
        .map((row) => ({
          id: row.id,
          name: row.name,
          detail: row.skillName
            ? `Handled by ${row.skillName}`
            : 'No matching trade — nobody is found for this',
          warning: !row.skillName,
        })),
    [all, typed]
  );

  // Filtering happens here rather than on the server because the whole list is
  // one small query per community and is already cached. The skill search is
  // remote for the opposite reason: that catalogue is global and grows.
  const hasExactMatch = all.some((row) => row.name.trim().toLowerCase() === typed);

  return (
    <TokenCombobox
      label="Complaint categories"
      required={required}
      selected={selected}
      suggestions={rows}
      hasExactMatch={hasExactMatch}
      isLoading={categories.isLoading}
      query={query}
      onQueryChange={setQuery}
      onSelect={(option) => onChange([...selected, { id: option.id, name: option.name }])}
      onCreate={(name) => onChange([...selected, { id: name, name }])}
      onRemove={(entry) => onChange(selected.filter((row) => row.id !== entry.id))}
      placeholder="e.g. Plumbing"
      addLabel="category"
      error={
        categories.isError
          ? categories.error?.message || 'Categories could not be loaded.'
          : ''
      }
    />
  );
}
