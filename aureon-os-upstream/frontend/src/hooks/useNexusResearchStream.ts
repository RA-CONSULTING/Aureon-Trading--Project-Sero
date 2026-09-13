import { useEffect, useRef, useState } from 'react';
import { readNexusObservation } from '@/lib/nexusObservation';

const DEFAULT_URL = import.meta.env.VITE_NEXUS_WS_URL || '';
type Receipt = { message: unknown; receivedAt: number };

/** One read-only connection; source timestamps remain distinct from transport state. */
export function useAurisWS(url = DEFAULT_URL) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aurisReceipt, setAuris] = useState<Receipt | null>(null);
  const [auraReceipt, setAura] = useState<Receipt | null>(null);
  const [, refreshAge] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    let alive = true;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const clearReadings = () => { setAuris(null); setAura(null); };
    function connect() {
      if (!alive) return;
      if (!url) {
        setConnected(false); clearReadings();
        setError('Auris and Aura require a commissioned sensor gateway.');
        return;
      }
      let ws: WebSocket;
      try {
        const target = new URL(url, window.location.href);
        const securePage = window.location.protocol === 'https:';
        if (target.host !== window.location.host || (securePage && target.protocol !== 'wss:')
          || (!securePage && !['ws:', 'wss:'].includes(target.protocol))) {
          throw new Error('research socket outside same-origin boundary');
        }
        ws = new WebSocket(target.toString());
      }
      catch { setError('Research socket URL unavailable'); return; }
      wsRef.current = ws;
      ws.onopen = () => { if (alive) { setConnected(true); setError(null); } };
      ws.onclose = () => {
        if (!alive) return;
        setConnected(false); clearReadings();
        retry = setTimeout(connect, 3_000);
      };
      ws.onerror = () => {
        if (!alive) return;
        setConnected(false); setError('Research socket unavailable'); clearReadings(); ws.close();
      };
      ws.onmessage = (event) => {
        if (!alive) return;
        try {
          const message: unknown = JSON.parse(event.data);
          if (!message || typeof message !== 'object') return;
          const type = (message as { type?: unknown }).type;
          const receipt = { message, receivedAt: Date.now() };
          if (type === 'auris_metrics') { setAuris(receipt); setError(null); }
          if (type === 'aura_features') { setAura(receipt); setError(null); }
        } catch { setError('Malformed research socket receipt'); clearReadings(); }
      };
    }
    connect();
    const ageTimer = setInterval(() => refreshAge((value) => value + 1), 1_000);
    return () => { alive = false; clearTimeout(retry); clearInterval(ageTimer); wsRef.current?.close(); wsRef.current = null; };
  }, [url]);
  return {
    connected, error, url: url || null, wsCtl: wsRef,
    auris: readNexusObservation(aurisReceipt?.message, 'auris_metrics', connected && !error, aurisReceipt?.receivedAt ?? null),
    aura: readNexusObservation(auraReceipt?.message, 'aura_features', connected && !error, auraReceipt?.receivedAt ?? null),
  };
}

