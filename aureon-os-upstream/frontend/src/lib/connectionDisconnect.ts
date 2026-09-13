export interface DisconnectableConnection {
  id: string;
  category: string;
  has_key: boolean;
  credential_management?: "account_keystore" | "instance_configuration" | "pinned_cloud_secret";
  credential_writable?: boolean;
}

export function connectionCanDisconnect(connection: DisconnectableConnection): boolean {
  return connection.has_key
    && connection.credential_writable !== false
    && connection.credential_management !== "pinned_cloud_secret";
}

export function connectionDisconnectPath(connection: Pick<DisconnectableConnection, "id" | "category">): string {
  const collection = connection.category === "ai_llm" ? "providers" : "connections";
  return `/api/${collection}/${encodeURIComponent(connection.id)}`;
}
