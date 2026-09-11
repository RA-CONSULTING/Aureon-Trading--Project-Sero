import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { readFreshBinanceTickers, tickerIsFresh, type FreshBinanceTicker } from '@/lib/freshTickerEvidence';

export function useFreshBinanceTickers(limit: number) {
  const [observed, setObserved] = useState<FreshBinanceTicker[]>([]);
  const [clock, setClock] = useState(Date.now);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const sequence = useRef(0);

  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setIsLoading(true);
    try {
      const { data, error } = await supabase.functions.invoke('fetch-all-tickers', {
        body: { exchanges: ['binance'], limit },
      });
      if (request !== sequence.current) return;
      const now = Date.now();
      const tickers = error ? [] : readFreshBinanceTickers(data, now);
      setObserved(tickers);
      setClock(now);
      setFetchError(tickers.length ? null : 'Fresh Binance market data is unavailable.');
    } catch {
      if (request !== sequence.current) return;
      setObserved([]);
      setFetchError('Fresh Binance market data is unavailable.');
    } finally {
      if (request === sequence.current) setIsLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    void refresh();
    const refreshTimer = setInterval(() => { void refresh(); }, 30_000);
    // Expire observations even while a provider request is stalled.
    const freshnessTimer = setInterval(() => setClock(Date.now()), 1_000);
    return () => {
      ++sequence.current;
      clearInterval(refreshTimer);
      clearInterval(freshnessTimer);
    };
  }, [refresh]);

  const tickers = useMemo(() => observed.filter(ticker => tickerIsFresh(ticker.sourceAt, clock)), [observed, clock]);
  const lastUpdate = tickers.length ? Math.max(...tickers.map(ticker => ticker.sourceAt)) : null;
  return {
    tickers, lastUpdate, isLoading, refresh,
    error: fetchError ?? (observed.length && !tickers.length ? 'Market observations have expired. Waiting for fresh data.' : null),
  };
}
