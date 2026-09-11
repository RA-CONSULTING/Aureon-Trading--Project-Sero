import { useEffect, useState } from 'react';
import { fetchUsgsEarthquakes, type UsgsSourceReceipt } from '@/lib/usgsPublicSource';
import { readUsgsObservation, USGS_POLL_INTERVAL_MS } from '@/lib/usgsObservationEvidence';

export function useUsgsEarthquakes() {
  const [receipt, setReceipt] = useState<UsgsSourceReceipt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const update = async () => {
      try {
        const result = await fetchUsgsEarthquakes(controller.signal);
        if (!controller.signal.aborted) { setReceipt(result); setError(null); setNow(Date.now()); }
      } catch (reason) {
        if (!controller.signal.aborted) {
          setReceipt(null);
          setError(reason instanceof Error ? reason.message : 'USGS observation feed unavailable');
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          timer = setTimeout(() => void update(), USGS_POLL_INTERVAL_MS);
        }
      }
    };
    void update();
    const expiry = setInterval(() => setNow(Date.now()), 5_000);
    return () => { controller.abort(); clearTimeout(timer); clearInterval(expiry); };
  }, []);
  const observation = receipt ? readUsgsObservation(receipt.payload, receipt.receivedAt, now) : null;
  return { observation, loading, error: error ?? (receipt && !observation ? 'USGS feed generation time has expired' : null) };
}
