import React from 'react';
import assert from 'node:assert/strict';
import test from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { AureonCodingOrganismConsole } from './AureonCodingOrganismConsole';
import { AureonGoldCapitalIntelligenceConsole } from './AureonGoldCapitalIntelligenceConsole';

test('unavailable coding services leave meaningful workspace controls disabled and no local approval writer', () => {
  const html = renderToStaticMarkup(<AureonCodingOrganismConsole />);
  assert.match(html, /aureon-glass-page-header/);
  assert.match(html, /Owner route unavailable/);
  assert.match(html, /Cloud coding worker not commissioned/);
  assert.match(html, /No prompt, chat, reload, autonomous job, repo mutation, proxy, or credential capability is exposed/);
  assert.match(html, /Refresh authenticated status/);
  assert.doesNotMatch(html, /Talk To Aureon|Reload Voice Worker|Full Coding Job|Send To Aureon|Approve|Request Revision|Reject/);
  assert.doesNotMatch(html, /127\.0\.0\.1:13002|localhost:13002/);
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
