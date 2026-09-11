import {
  NOAA_FEEDS, NOAA_REQUEST_TIMEOUT_MS, NOAA_RESPONSE_MAX_BYTES,
  emptyNoaaReceipt, readNoaaFeed, type NoaaFeed, type NoaaReceipt,
} from './noaaObservationEvidence';

/** Read only the allowlisted public product; never retain a full response in React state. */
export async function fetchNoaaFeed(
  feed: NoaaFeed, signal: AbortSignal, fetcher: typeof fetch = fetch, now: () => number = Date.now,
): Promise<NoaaReceipt> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) controller.abort();
  const timeout = setTimeout(abort, NOAA_REQUEST_TIMEOUT_MS);
  try {
    const requestUrl = fetcher === fetch ? `/api/research/noaa/${feed}` : NOAA_FEEDS[feed].url;
    const response = await fetcher(requestUrl, {
      method: 'GET', credentials: 'omit', cache: 'no-cache', signal: controller.signal,
    });
    if (!response.ok) throw new Error(`NOAA HTTP ${response.status}`);
    if (Number(response.headers.get('Content-Length')) > NOAA_RESPONSE_MAX_BYTES) {
      await response.body?.cancel();
      throw new Error('NOAA response exceeds the 8 MiB limit');
    }
    if (!response.body) throw new Error('NOAA response body unavailable');
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    try {
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        total += result.value.byteLength;
        if (total > NOAA_RESPONSE_MAX_BYTES) {
          await reader.cancel();
          throw new Error('NOAA response exceeds the 8 MiB limit');
        }
        chunks.push(result.value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    const payload: unknown = JSON.parse(new TextDecoder().decode(bytes));
    if (controller.signal.aborted) throw new Error('NOAA request cancelled');
    const receipt = payload as Partial<NoaaReceipt>;
    if (requestUrl.startsWith('/api/') && receipt?.feed === feed && Array.isArray(receipt.samples)) {
      return {
        feed,
        status: receipt.status === 'observed' || receipt.status === 'loading' || receipt.status === 'unavailable' ? receipt.status : 'unavailable',
        receivedAt: typeof receipt.receivedAt === 'number' ? receipt.receivedAt : null,
        samples: receipt.samples,
        reason: typeof receipt.reason === 'string' ? receipt.reason : 'NOAA local gateway receipt',
      };
    }
    return readNoaaFeed(feed, payload, now());
  } catch (error) {
    return emptyNoaaReceipt(feed, false, controller.signal.aborted ? 'NOAA request timed out or cancelled'
      : error instanceof Error ? error.message : 'NOAA source request failed');
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener('abort', abort);
  }
}
