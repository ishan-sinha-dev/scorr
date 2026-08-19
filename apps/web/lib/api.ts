import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

/**
 * Fetch wrapper for apps/api, server-side only (reads the session via
 * next/headers cookies — see lib/supabase/server.ts). Attaches the
 * caller's own Supabase access token; apps/api uses it to enforce RLS,
 * it never talks to Supabase with a service-role key on the user's
 * behalf. See docs/architecture/phase0-assessment.md for why writes go
 * through apps/api rather than straight from here to Supabase.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("Not authenticated");
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${env.apiUrl()}${path}`, { ...init, headers, cache: "no-store" });
}
