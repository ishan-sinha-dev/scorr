import { createBrowserClient } from "@supabase/ssr";

import { env } from "@/lib/env";

/**
 * Browser-side Supabase client, for use in Client Components. Most of
 * Phase 2's UI is server-rendered and doesn't need this — it exists for
 * whatever later phase needs client-side auth state (e.g. reacting to
 * sign-out without a full page reload).
 */
export function createClient() {
  return createBrowserClient(env.supabaseUrl(), env.supabaseAnonKey());
}
