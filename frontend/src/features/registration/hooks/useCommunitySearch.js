import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { registrationApi } from '../registrationApi';
import { useAuthStore } from '../../../store/authStore';
import { QUERY_POLICIES, PAGINATED } from '../../../lib/api/queryClient';

function useDebouncedValue(value, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timeout);
  }, [value, delay]);
  return debounced;
}

export function useCommunitySearch(rawQuery) {
  const query = useDebouncedValue(rawQuery.trim());
  const identityId = useAuthStore((state) => state.sessionContext?.identity?.id || 'anonymous');
  return useQuery({
    queryKey: ['community-search', identityId, query],
    enabled: query.length >= 2,
    queryFn: ({ signal }) => registrationApi.searchCommunities({ query, signal }),
    // A geo/community lookup: the named reference-data domain, plus keeping
    // the previous keystroke's matches on screen while the next resolves.
    ...QUERY_POLICIES.reference,
    ...PAGINATED,
  });
}
