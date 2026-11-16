import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from '@/lib/api'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    retry: 0,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  })
}
