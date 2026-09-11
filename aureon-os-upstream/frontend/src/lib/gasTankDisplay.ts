/** Initial hook defaults are not a successfully observed account balance. */
export function gasTankReceiptIsCurrent(observed: boolean, receivedAt: number | null, nowMs = Date.now()): boolean {
  return observed && receivedAt !== null && Number.isFinite(receivedAt)
    && receivedAt <= nowMs + 5_000 && nowMs - receivedAt <= 300_000;
}

export function gasTankMoney(value: unknown, receiptObserved: boolean): string {
  return receiptObserved && typeof value === 'number' && Number.isFinite(value)
    ? `£${value.toFixed(2)}` : 'Unavailable';
}
