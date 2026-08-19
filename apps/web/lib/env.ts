function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

/**
 * Centralized env var access — fail fast with a clear message instead of
 * letting `undefined` silently flow into the Supabase SDK and fail later
 * with a cryptic error.
 */
export const env = {
  supabaseUrl: () => requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
  supabaseAnonKey: () => requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
  apiUrl: () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
};
