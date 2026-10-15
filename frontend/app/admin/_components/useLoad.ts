"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

export function messageOf(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

// Load data when the page opens or its inputs change. `reload` fetches again
// (keeping what is on screen until the new data arrives). The loader must be
// stable, so wrap it in useCallback with the inputs it uses.
export function useLoad<T>(loader: () => Promise<T>, fallback: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    loader().then(
      (loaded) => {
        if (cancelled) return;
        setData(loaded);
        setError(null);
      },
      (err) => {
        if (!cancelled) setError(messageOf(err, fallback));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [loader, fallback, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, reload, setData };
}
