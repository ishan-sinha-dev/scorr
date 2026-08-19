import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
        SOCRR
      </span>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">
        SOC Report Reviewer
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Evidence-linked control intelligence for SOC report review.
      </p>
      <Link
        href="/login"
        className="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
      >
        Sign in
      </Link>
    </div>
  );
}
