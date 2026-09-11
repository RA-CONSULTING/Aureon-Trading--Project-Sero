/** Local conversation state is scoped to the current authentication invalidation epoch. */
export interface OperatorChatSession<T> {
  version: number;
  turns: T[];
  input: string;
  busy: boolean;
}

export function emptyChatSession<T>(version: number): OperatorChatSession<T> {
  return { version, turns: [], input: '', busy: false };
}

/** Hide a previous account's transcript synchronously, before effect cleanup runs. */
export function chatSessionForVersion<T>(session: OperatorChatSession<T>, version: number): OperatorChatSession<T> {
  return session.version === version ? session : emptyChatSession<T>(version);
}

export function appendChatSessionTurn<T>(session: OperatorChatSession<T>, version: number, turn: T): OperatorChatSession<T> {
  return session.version === version ? { ...session, turns: [...session.turns, turn] } : session;
}
