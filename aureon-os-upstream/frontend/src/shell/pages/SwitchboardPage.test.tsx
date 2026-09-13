import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { LegacyReleaseDiagnosticPanel, SwitchboardConfigurationCards } from './SwitchboardPage';
import { readSwitchboardConfiguration, type SwitchboardFlag } from '../../lib/platformConfiguration';
import type { ReleaseReadinessReceipt } from '../../lib/operatorReleaseReadiness';

function configuration() {
  const common: SwitchboardFlag = { id: 'ON_FLAG', env_var: 'ON_FLAG', label: 'Observed on', group: 'Actual registered group',
    kind: 'safe', effect: 'live', effect_note: 'Operator immediate', description: 'Real backend description',
    default: false, enabled: true, stored: false, source: 'store', risk_value: true, armed: false,
    requested_armed: false, decided_at: 1788808944, pending_restart: false, pending_handoff: false, env_hold: false };
  return readSwitchboardConfiguration({ groups: [{ label: common.group, flags: [common,
    { ...common, id: 'OFF_FLAG', env_var: 'OFF_FLAG', label: 'Observed off', enabled: false, stored: true,
      kind: 'hard_boundary', effect: 'restart', requested_armed: true, pending_restart: null },
  ] }], summary: { total: 2, enabled: 1, requested_enabled: 1, armed: 0, requested_armed: 1,
    pending_restart: 0, pending_handoff: 0, hard_boundary_total: 1 } });
}

test('glass cards render observed ON/OFF settings and unknown restart status without example capabilities', () => {
  const html = renderToStaticMarkup(<SwitchboardConfigurationCards configuration={configuration()} canManage saving={null} onToggle={() => { throw new Error('Render must never mutate'); }} />);
  assert.match(html, /Actual registered group/);
  assert.match(html, /aria-checked="true"/);
  assert.match(html, /aria-checked="false"/);
  assert.match(html, /Restart status unknown/);
  assert.match(html, /Saved intent ON differs from effective operator configuration OFF/);
  assert.match(html, /Saved intent OFF differs from effective operator configuration ON/);
  assert.doesNotMatch(html, /EXAMPLE|ALL OFF|aspirational|disabled=""/);
});

test('all configuration switches become unavailable for a view-only session or a pending save', () => {
  for (const props of [{ canManage: false, saving: null }, { canManage: true, saving: 'ON_FLAG' }]) {
    const html = renderToStaticMarkup(<SwitchboardConfigurationCards configuration={configuration()} {...props} onToggle={() => { throw new Error('Render must never mutate'); }} />);
    assert.equal((html.match(/disabled=""/g) ?? []).length, 2);
    assert.equal((html.match(/role="switch"/g) ?? []).length, 2);
  }
});

test('legacy held checklist is diagnostic and appears after the operative signed cloud controller', () => {
  const now = Date.now();
  const legacyReceipt = {
    data: {
      requirements: [],
      work_orders: [{ status: 'not_integrated' }],
    },
    loading: false, error: null, httpStatus: null, isReceiptCurrent: true, lastReceivedAt: now,
  } as unknown as ReleaseReadinessReceipt;
  const html = renderToStaticMarkup(<LegacyReleaseDiagnosticPanel receipt={legacyReceipt} />);
  assert.match(html, /Legacy local release checklist · diagnostic only/);
  assert.match(html, /does not decide cloud trading authority/);
  assert.match(html, /signed cloud controller panel is the operative release status/);
  assert.doesNotMatch(html, />Live release gate</);

  const source = readFileSync(new URL('./SwitchboardPage.tsx', import.meta.url), 'utf8');
  assert.match(source, /Signed cloud trading authority · operative status/);
  assert.ok(source.indexOf('<CloudTradingControlPanel') < source.indexOf('<LegacyReleaseDiagnosticPanel'));
});
