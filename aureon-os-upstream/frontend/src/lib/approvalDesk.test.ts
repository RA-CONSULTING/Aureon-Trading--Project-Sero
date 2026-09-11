import assert from "node:assert/strict";
import test from "node:test";
import { parseApprovalDesk, requirePendingApproval } from "./approvalDesk.ts";

const item = { id: "fixture-1", kind: "fixture", summary: "Offline fixture", prepared_by: "fixture", risk: "low", status: "pending" };
test("only an observed valid empty queue is an empty desk", () => {
  assert.deepEqual(parseApprovalDesk({ pending: [], recent: [] }), { pending: [], recent: [] });
  for (const value of [null, {}, { pending: [], recent: [], error: "read failed" }, { pending: "", recent: [] },
    { pending: [{ ...item, status: "approved" }], recent: [] }, { pending: [item, item], recent: [] }]) {
    assert.throws(() => parseApprovalDesk(value));
  }
});
test("preflight requires the selected item to remain pending in the new queue", () => {
  const before = parseApprovalDesk({ pending: [item], recent: [] });
  assert.doesNotThrow(() => requirePendingApproval(before, item.id));
  const after = parseApprovalDesk({ pending: [], recent: [{ ...item, status: "approved" }] });
  assert.throws(() => requirePendingApproval(after, item.id), /no longer awaiting/);
});
