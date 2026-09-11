export interface ApprovalItem {
  id: string;
  kind: string;
  summary: string;
  prepared_by: string;
  risk: string;
  status: "pending" | "approved" | "rejected";
  note?: string;
}
export interface ApprovalDesk { pending: ApprovalItem[]; recent: ApprovalItem[]; }

/** A transport success with an error payload must never become an empty desk. */
export function parseApprovalDesk(value: unknown): ApprovalDesk {
  if (!value || typeof value !== "object") throw new Error("Invalid approval queue response");
  const record = value as Record<string, unknown>;
  if (record.error) throw new Error("The gateway could not read the approval queue");
  function items(value: unknown, pending: boolean): ApprovalItem[] {
    if (!Array.isArray(value) || !value.every(item => item && typeof item === "object"
      && ["id", "kind", "summary", "prepared_by", "risk"].every(key => typeof item[key] === "string")
      && item.id.trim().length > 0
      && (pending ? item.status === "pending" : ["pending", "approved", "rejected"].includes(item.status))
      && (item.note === undefined || typeof item.note === "string"))) {
      throw new Error("Invalid approval queue entries");
    }
    if (new Set(value.map(item => item.id)).size !== value.length) throw new Error("Duplicate approval queue entries");
    return value as ApprovalItem[];
  }
  return { pending: items(record.pending, true), recent: items(record.recent, false) };
}

export function requirePendingApproval(desk: ApprovalDesk, id: string): void {
  if (!desk.pending.some(item => item.id === id && item.status === "pending")) {
    throw new Error("This item is no longer awaiting a decision. Refreshing the desk.");
  }
}
