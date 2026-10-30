/** Request short-lived, read-only Google Calendar Free/Busy access. */
export const GOOGLE_FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy";

export type GoogleCalendarSession = {accessToken: string; expiresAt: number};

type TokenResponse = {access_token?: string; expires_in?: number; error?: string};
type TokenClient = {requestAccessToken: (options?: {prompt?: string}) => void};
type GoogleIdentity = {accounts: {oauth2: {initTokenClient: (options: {
  client_id: string; scope: string; callback: (response: TokenResponse) => void;
  error_callback?: (error: {type: string}) => void;
}) => TokenClient}}};

declare global {interface Window {google?: GoogleIdentity}}

let ready: Promise<void> | null = null;
export function preloadGoogleCalendar(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Google Calendar is available in the browser only"));
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  if (!ready) {
    ready = new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = () => window.google?.accounts?.oauth2 ? resolve() : reject(new Error("Google sign-in failed to initialize"));
      script.onerror = () => reject(new Error("Could not load Google sign-in"));
      document.head.appendChild(script);
    }).catch(error => {ready = null; throw error;});
  }
  return ready;
}

export async function requestGoogleCalendarAccess(clientId: string): Promise<GoogleCalendarSession> {
  if (!clientId.trim()) throw new Error("Set NEXT_PUBLIC_HOMHIVE_GOOGLE_CLIENT_ID in frontend/.env.local and restart Next.js");
  await preloadGoogleCalendar();
  const oauth = window.google?.accounts.oauth2;
  if (!oauth) throw new Error("Google sign-in is unavailable");
  return new Promise<GoogleCalendarSession>((resolve, reject) => {
    const tokenClient = oauth.initTokenClient({
      client_id: clientId,
      scope: GOOGLE_FREEBUSY_SCOPE,
      callback: response => {
        if (response.error || !response.access_token || !Number.isFinite(Number(response.expires_in))) {
          reject(new Error("Google Calendar permission was not granted"));
        } else {
          resolve({accessToken: response.access_token, expiresAt: Date.now() + Number(response.expires_in) * 1000});
        }
      },
      error_callback: () => reject(new Error("Google sign-in was cancelled or blocked")),
    });
    tokenClient.requestAccessToken({prompt: "consent"});
  });
}
