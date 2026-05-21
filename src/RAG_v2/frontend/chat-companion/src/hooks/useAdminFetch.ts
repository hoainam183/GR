import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';

interface UseAdminFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Shared fetch hook with loading, error, and empty state handling.
 * Automatically shows toast on error.
 */
export function useAdminFetch<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseAdminFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result);
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        const message = err instanceof Error ? err.message : 'Không thể tải dữ liệu';
        setError(message);
        toast.error(message);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    return () => { mountedRef.current = false; };
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
