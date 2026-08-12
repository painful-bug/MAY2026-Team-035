import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { departmentsApi } from '../departmentsApi';
import TokenCombobox from './TokenCombobox';
import { useDebounced } from './useDebounced';

// The skill field, in two modes.
//
// **Deferred** (`departmentId` absent) — the department does not exist yet, so
// there is nothing to attach to. Selections are held by the caller and saved
// with `PUT /departments/{id}/skills` once the create returns an id. Creating a
// brand-new trade still writes to the catalogue immediately, through
// `POST /skills`: the catalogue is global and the word is useful to everybody
// whether or not this particular form is ever submitted.
//
// **Live** (`departmentId` present) — every change is a call. Adding by name
// goes through `POST /departments/{id}/skills`, which creates and attaches in
// one transaction; removing goes through the DELETE. This is the mode the
// manager's screen uses, where "newly created skills get auto-added to the
// department" is not a separate step but the endpoint's whole behaviour.

export default function SkillPicker({
  departmentId = null,
  selected,
  onChange,
  label = 'Skills this department needs',
  required = false,
}) {
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const debounced = useDebounced(query);
  const queryClient = useQueryClient();

  const suggestions = useQuery({
    queryKey: ['skills', 'search', debounced],
    queryFn: () => departmentsApi.searchSkills(debounced),
    enabled: debounced.trim().length > 0,
    staleTime: 30_000,
  });

  const rows = suggestions.data || [];

  // The server's answer, not ours. See the header of TokenCombobox for why this
  // is never recomputed from `rows` by comparing strings here.
  const hasExactMatch = rows.some(
    (row) => row.name.trim().toLowerCase() === debounced.trim().toLowerCase()
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['skills'] });
    if (departmentId) {
      queryClient.invalidateQueries({ queryKey: ['departments'] });
    }
  };

  const create = useMutation({
    mutationFn: (name) =>
      departmentId
        ? departmentsApi.addDepartmentSkill(departmentId, name)
        : departmentsApi.createSkill({ name }),
    onSuccess: (skill) => {
      setError('');
      // The response carries the *stored* spelling, which is not always what was
      // typed — an existing "Plumbing" answers a typed "plumbing". Adding the
      // response rather than the query is what keeps one name on the chip and
      // in the database.
      if (!selected.some((entry) => entry.id === skill.id)) {
        onChange([...selected, { id: skill.id, name: skill.name }]);
      }
    },
    onError: (err) => setError(err?.message || 'That skill could not be added.'),
  });

  const attach = useMutation({
    mutationFn: (skill) =>
      departmentId
        ? departmentsApi.addDepartmentSkill(departmentId, skill.name)
        : Promise.resolve(skill),
    onSuccess: (_result, skill) => {
      setError('');
      onChange([...selected, { id: skill.id, name: skill.name }]);
      invalidate();
    },
    onError: (err) => setError(err?.message || 'That skill could not be added.'),
  });

  const detach = useMutation({
    mutationFn: (skill) =>
      departmentId
        ? departmentsApi.removeDepartmentSkill(departmentId, skill.id)
        : Promise.resolve(skill),
    onSuccess: (_result, skill) => {
      setError('');
      onChange(selected.filter((entry) => entry.id !== skill.id));
      invalidate();
    },
    onError: (err) => setError(err?.message || 'That skill could not be removed.'),
  });

  return (
    <TokenCombobox
      label={label}
      required={required}
      selected={selected}
      suggestions={rows.map((row) => ({
        id: row.id,
        name: row.name,
        detail: row.category && row.category !== 'other' ? row.category : '',
      }))}
      hasExactMatch={hasExactMatch}
      isLoading={suggestions.isFetching}
      query={query}
      onQueryChange={setQuery}
      onSelect={(option) => attach.mutate(option)}
      onCreate={(name) => create.mutate(name)}
      onRemove={(skill) => detach.mutate(skill)}
      placeholder="e.g. Plumbing"
      addLabel="skill"
      busy={create.isPending || attach.isPending}
      error={error}
    />
  );
}
