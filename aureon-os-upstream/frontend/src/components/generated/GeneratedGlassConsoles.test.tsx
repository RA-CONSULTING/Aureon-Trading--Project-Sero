import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { AureonCodingOrganismConsole } from './AureonCodingOrganismConsole';
import { AureonGoldCapitalIntelligenceConsole } from './AureonGoldCapitalIntelligenceConsole';

test('unavailable coding services leave meaningful workspace controls disabled and no local approval writer', () => {
  const html = renderToStaticMarkup(<AureonCodingOrganismConsole />);
  assert.match(html, /aureon-glass-page-header/);
  assert.match(html, /Coding hub unavailable/);
  assert.match(html, /Cadence unavailable/);
  assert.match(html, /does not provide a persistent approval endpoint/);
  const buttons = html.match(/<button\b[^>]*>[\s\S]*?<\/button>/g) ?? [];
  for (const label of ['Talk To Aureon', 'Reload Voice Worker', 'Full Coding Job', 'Send To Aureon', 'Approve', 'Request Revision', 'Reject']) {
    const button = buttons.find(item => item.includes(label));
    assert.ok(button, label);
    assert.match(button, /disabled=""/, label);
  }
  assert.doesNotMatch(html, /0\.00Hz|system active/);
});

test('gold observation surface survives missing recorded report without invented price or permission', () => {
  const html = renderToStaticMarkup(<AureonGoldCapitalIntelligenceConsole />);
  assert.match(html, /aureon-glass-page-header/);
  assert.match(html, /Current gold observations/);
  assert.match(html, /Runtime proof unavailable/);
  assert.match(html, /Report unavailable/);
  assert.doesNotMatch(html, /live trade allowed|TRADEABLE|\$0\.00/);
});
