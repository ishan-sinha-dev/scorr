import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="border-b border-border px-6 py-3">
        <span className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          SOCRR
        </span>
      </header>
      <main className="flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
