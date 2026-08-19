import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { env } from "@/lib/env";

/**
 * Server-side Supabase client (Server Components, Server Actions, Route
 * Handlers), backed by the request's cookies. This is what auth.ts and
 * lib/api.ts use to read the current session.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(env.supabaseUrl(), env.supabaseAnonKey(), {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          );
        } catch {
          // Called from a Server Component that can't set cookies directly.
          // Harmless as long as middleware.ts is refreshing the session.
        }
      },
    },
  });
}
