import { signIn, signUp } from "./actions";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; message?: string }>;
}) {
  const params = await searchParams;

  return (
    <div className="flex min-h-full flex-1 items-center justify-center bg-background px-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            SOCRR
          </span>
          <h1 className="mt-1 text-xl font-semibold text-foreground">Sign in</h1>
        </div>

        {params.error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {params.error}
          </p>
        )}
        {params.message && (
          <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
            {params.message}
          </p>
        )}

        <form className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium text-foreground">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium text-foreground">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={6}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            />
          </div>
          <div className="flex gap-2">
            <button
              formAction={signIn}
              className="flex-1 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
            >
              Sign in
            </button>
            <button
              formAction={signUp}
              className="flex-1 rounded-md border border-input px-3 py-2 text-sm font-medium text-foreground"
            >
              Sign up
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
