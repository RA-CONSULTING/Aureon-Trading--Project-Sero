export interface LocalSignOutOptions { scope: 'local' }

type SignOutResult = { error?: unknown };
type SignOut = (options: LocalSignOutOptions) => Promise<SignOutResult>;

/** End only the Supabase session held by this browser context. */
export async function endTenantBrowserSession(signOut: SignOut): Promise<void> {
  const result = await signOut({ scope: 'local' });
  if (!result?.error) return;
  if (result.error instanceof Error) throw result.error;
  throw new Error('Tenant session sign out was not confirmed');
}
