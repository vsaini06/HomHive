export const ACCOUNT_SESSION_KEY = "homhive:account-session:v1";

export type AccountSession = {
  apiUrl: string;
  householdId: string;
  accessToken: string;
  expiresAt: string;
};

type SessionStore = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function clearAccountSession(store: SessionStore): void {
  store.removeItem(ACCOUNT_SESSION_KEY);
}

export function saveAccountSession(store: SessionStore, session: AccountSession): void {
  store.setItem(ACCOUNT_SESSION_KEY, JSON.stringify(session));
}

export function readAccountSession(store: SessionStore, expectedApiUrl: string, now = Date.now()): AccountSession | null {
  const saved = store.getItem(ACCOUNT_SESSION_KEY);
  if (!saved) return null;
  try {
    const parsed: unknown = JSON.parse(saved);
    if (!parsed || typeof parsed !== "object") throw new Error("Invalid account session");
    const data = parsed as Record<string, unknown>;
    if (typeof data.apiUrl !== "string" || data.apiUrl.replace(/\/$/, "") !== expectedApiUrl.replace(/\/$/, "")
      || typeof data.householdId !== "string" || !/^home_[a-f0-9]{32}$/.test(data.householdId)
      || typeof data.accessToken !== "string" || data.accessToken.length < 30 || data.accessToken.length > 200
      || typeof data.expiresAt !== "string") throw new Error("Invalid account session");
    const expires = Date.parse(data.expiresAt);
    if (!Number.isFinite(expires) || expires <= now) throw new Error("Expired account session");
    return {
      apiUrl: data.apiUrl as string,
      householdId: data.householdId as string,
      accessToken: data.accessToken as string,
      expiresAt: data.expiresAt as string,
    };
  } catch {
    clearAccountSession(store);
    return null;
  }
}
