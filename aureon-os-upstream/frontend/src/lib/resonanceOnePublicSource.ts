import { RESONANCE_ONE_SOURCE, readResonanceOneObservation } from './resonanceOneEvidence';

export const RESONANCE_ONE_MAX_BYTES = 1024 * 1024;
export type ResonanceOneReceipt = { payload: unknown; receivedAt: number };

export async function fetchResonanceOne(signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<ResonanceOneReceipt> {
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const requestUrl = fetcher === fetch ? '/api/research/resonance-one' : RESONANCE_ONE_SOURCE;
    const response = await fetcher(requestUrl, { signal: controller.signal, credentials: 'omit', cache: 'default' });
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error(`ResonanceOne source HTTP ${response.status}`);
    }
    if (!response.body) throw new Error('ResonanceOne source response body unavailable');
    if (Number(response.headers.get('content-length')) > RESONANCE_ONE_MAX_BYTES) {
      await response.body.cancel();
      throw new Error('ResonanceOne source exceeded response size limit');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8', { fatal: true });
    let body = '';
    let bytes = 0;
    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        bytes += chunk.value.byteLength;
        if (bytes > RESONANCE_ONE_MAX_BYTES) {
          await reader.cancel();
          throw new Error('ResonanceOne source exceeded response size limit');
        }
        body += decoder.decode(chunk.value, { stream: true });
      }
      body += decoder.decode();
    } catch (error) {
      await reader.cancel(error);
      throw error;
    } finally { reader.releaseLock(); }
    const payload: unknown = JSON.parse(body);
    const gatewayReceipt = payload as Partial<ResonanceOneReceipt> & { available?: boolean; reason?: string };
    const sourcePayload = requestUrl.startsWith('/api/') && 'payload' in gatewayReceipt ? gatewayReceipt.payload : payload;
    const receivedAt = requestUrl.startsWith('/api/') && typeof gatewayReceipt.receivedAt === 'number' ? gatewayReceipt.receivedAt : Date.now();
    if (!readResonanceOneObservation(sourcePayload, receivedAt)) throw new Error(typeof gatewayReceipt.reason === 'string' ? gatewayReceipt.reason : 'ResonanceOne report is stale, incomplete or malformed');
    return { payload: sourcePayload, receivedAt };
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
