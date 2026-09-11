import { useEffect, useState } from 'react';
import { fetchResonanceOne, type ResonanceOneReceipt } from '@/lib/resonanceOnePublicSource';
import { readResonanceOneObservation, RESONANCE_ONE_POLL_MS } from '@/lib/resonanceOneEvidence';

export function useResonanceOne() {
  const [receipt, setReceipt] = useState<ResonanceOneReceipt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const update = async () => {
      try {
        const result = await fetchResonanceOne(controller.signal);
        if (!controller.signal.aborted) { setReceipt(result); setError(null); setNow(Date.now()); }
      } catch (reason) {
        if (!controller.signal.aborted) {
          setReceipt(null);
          setError(reason instanceof Error ? reason.message : 'ResonanceOne reported index unavailable');
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          timer = setTimeout(() => void update(), RESONANCE_ONE_POLL_MS);
        }
      }
    };
    void update();
    const expiry = setInterval(() => setNow(Date.now()), 5_000);
    return () => { controller.abort(); clearTimeout(timer); clearInterval(expiry); };
  }, []);
  const observation = receipt ? readResonanceOneObservation(receipt.payload, receipt.receivedAt, now) : null;
  return { observation, loading, error: error ?? (receipt && !observation ? 'The provider update or observation window has expired' : null) };
}
