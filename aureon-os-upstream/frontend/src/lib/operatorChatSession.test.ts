import assert from 'node:assert/strict';
import test from 'node:test';
import { appendChatSessionTurn, chatSessionForVersion, emptyChatSession } from './operatorChatSession';

test('authentication reset immediately hides transcript, unsent input and pending indicator', () => {
  const previous = { version: 3, turns: ['private prompt', 'private reply'], input: 'unsent private draft', busy: true };
  assert.equal(chatSessionForVersion(previous, 3), previous);
  assert.deepEqual(chatSessionForVersion(previous, 4), emptyChatSession(4));
});

test('a late reply or request error from the previous account cannot enter the new conversation', () => {
  const current = appendChatSessionTurn(emptyChatSession<string>(4), 4, 'current account prompt');
  assert.equal(appendChatSessionTurn(current, 3, 'old private reply'), current);
  assert.equal(appendChatSessionTurn(current, 3, 'old private error'), current);
  assert.deepEqual(appendChatSessionTurn(current, 4, 'current reply').turns, ['current account prompt', 'current reply']);
});
