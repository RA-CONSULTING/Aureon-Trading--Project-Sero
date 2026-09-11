import { USGS_EARTHQUAKE_SOURCE, readUsgsObservation } from './usgsObservationEvidence';

export const USGS_MAX_RESPONSE_BYTES = 8 * 1024 * 1024;
export type UsgsSourceReceipt = { payload: unknown; receivedAt: number };

/** Public USGS GET only, with a bounded streamed body and transport timeout. */
export async function fetchUsgsEarthquakes(signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<UsgsSourceReceipt> {
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const requestUrl = fetcher === fetch ? '/api/research/usgs-earthquakes' : USGS_EARTHQUAKE_SOURCE;
    const response = await fetcher(requestUrl, { signal: controller.signal, credentials: 'omit', cache: 'no-cache' });
    if (!response.ok) throw new Error(`USGS source HTTP ${response.status}`);
    if (!response.body) throw new Error('USGS source response body unavailable');
    if (Number(response.headers.get('content-length')) > USGS_MAX_RESPONSE_BYTES) {
      await response.body.cancel();
      throw new Error('USGS source exceeded response size limit');
    }
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > USGS_MAX_RESPONSE_BYTES) {
          await reader.cancel();
          throw new Error('USGS source exceeded response size limit');
        }
        chunks.push(chunk.value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const payload: unknown = JSON.parse(new TextDecoder().decode(bytes));
    const gatewayReceipt = payload as Partial<UsgsSourceReceipt> & { available?: boolean; reason?: string };
    const sourcePayload = requestUrl.startsWith('/api/') && 'payload' in gatewayReceipt ? gatewayReceipt.payload : payload;
    const receivedAt = requestUrl.startsWith('/api/') && typeof gatewayReceipt.receivedAt === 'number' ? gatewayReceipt.receivedAt : Date.now();
    if (!readUsgsObservation(sourcePayload, receivedAt)) throw new Error(typeof gatewayReceipt.reason === 'string' ? gatewayReceipt.reason : 'USGS source is stale, incomplete or malformed');
    return { payload: sourcePayload, receivedAt };
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
