"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

/**
 * GET a JSON resource. `reload()` refetches without flipping `loading`, so polling and
 * post-action refreshes do not flash a spinner. Pass `null` to skip the request.
 */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(path !== null);
  const current = useRef(path);
  current.current = path;

  const load = useCallback(async (p: string) => {
    try {
      const result = await api<T>(p);
      if (current.current === p) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (current.current === p) setError(e);
    } finally {
      if (current.current === p) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (path === null) return;
    setLoading(true);
    void load(path);
  }, [path, load]);

  const reload = useCallback(() => (current.current ? load(current.current) : Promise.resolve()), [load]);

  return { data, error, loading, reload, setData };
}
