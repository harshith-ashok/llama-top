import { useQuery } from "@tanstack/react-query"

/** Poll an API call on an interval so dashboards stay live without WebSockets. */
export function useLive<T>(key: unknown[], fn: () => Promise<T>, intervalMs = 5000) {
  return useQuery({ queryKey: key, queryFn: fn, refetchInterval: intervalMs })
}
