import { useState, useEffect } from 'react';
import { readSchumannObservation, type SchumannData } from '@/lib/earthObservationEvidence';
export type { SchumannData, SchumannHarmonic } from '@/lib/earthObservationEvidence';

/** Direct observations only. NOAA-derived proxies cannot establish station measurements. */
export function useSchumannResonance() {
  const [schumannData, setSchumannData] = useState<SchumannData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    const aborter = new AbortController();
    let inFlight = false;
    let lastPayload: unknown = null;
    let history: number[][] = [];
    let lastObservation = 0;
    const update = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await fetch('/api/research/schumann', {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-cache',
          signal: aborter.signal,
        });
        if (!response.ok) throw new Error(`Schumann gateway returned HTTP ${response.status}`);
        const data = await response.json();
        if (cancelled) return;
        lastPayload = data;
        const observation = readSchumannObservation(data);
        if (!observation) {
          setSchumannData(null);
          setError('Fresh direct Schumann station activity unavailable; NOAA/Kp proxies are not station observations.');
          return;
        }
        if (observation.timestamp.getTime() !== lastObservation) {
          if (observation.harmonics.length) history = [...history, observation.harmonics.map(item => item.amplitude)].slice(-100);
          lastObservation = observation.timestamp.getTime();
        }
        setSchumannData({ ...observation, spectrumHistory: history });
        setError(null);
      } catch {
        if (!cancelled) {
          lastPayload = null;
          setSchumannData(null);
          setError('Direct Schumann observation feed unavailable.');
        }
      } finally { inFlight = false; }
    };
    void update();
    const poll = setInterval(() => {
      if (!readSchumannObservation(lastPayload)) setSchumannData(null);
      void update();
    }, 60_000);
    return () => { cancelled = true; aborter.abort(); clearInterval(poll); };
  }, []);
  return { schumannData, isConnected: schumannData !== null, dataSource: schumannData?.dataSource ?? 'UNAVAILABLE', error };
}
