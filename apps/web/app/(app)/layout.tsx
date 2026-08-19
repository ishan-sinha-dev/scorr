import { Building2, LogOut, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";
import { signOut } from "./actions";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-full flex-1">
      <aside className="flex w-14 flex-col items-center border-r border-border bg-card py-4">
        <Link
          href="/organizations"
          className="flex h-9 w-9 items-center justify-center rounded-md text-primary"
          title="SOCRR"
        >
          <ShieldCheck className="h-6 w-6" />
        </Link>
        <nav className="mt-6 flex flex-1 flex-col items-center gap-1">
          <Link
            href="/organizations"
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Organizations"
          >
            <Building2 className="h-5 w-5" />
          </Link>
        </nav>
        <form action={signOut}>
          <button
            type="submit"
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-destructive"
            title="Sign out"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </form>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
          <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            SOCRR
          </span>
          <span className="text-xs text-muted-foreground">{user.email}</span>
        </header>
        <main className="flex-1 bg-background px-6 py-8">{children}</main>
      </div>
    </div>
  );
}
