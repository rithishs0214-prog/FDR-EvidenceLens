import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> { data: T | null; error: string | null; loading: boolean; reload: () => void }

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], pollMs?: (data: T | null) => number | null): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const pollRef = useRef(pollMs);
  pollRef.current = pollMs;

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const run = (initial: boolean) => {
      if (initial) setLoading(true);
      fnRef.current()
        .then((d) => {
          if (cancelled) return;
          setData(d); setError(null); setLoading(false);
          const next = pollRef.current?.(d) ?? null;
          if (next) timer = window.setTimeout(() => run(false), next);
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          setError(e instanceof Error ? e.message : "Something went wrong."); setLoading(false);
        });
    };
    run(true);
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = window.setTimeout(() => setV(value), ms); return () => window.clearTimeout(t); }, [value, ms]);
  return v;
}
