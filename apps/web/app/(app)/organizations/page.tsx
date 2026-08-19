import Link from "next/link";

import { apiFetch } from "@/lib/api";
import { createOrganization } from "./actions";

type Organization = {
  id: string;
  name: string;
  created_at: string;
};

export default async function OrganizationsPage() {
  const response = await apiFetch("/organizations");
  const organizations: Organization[] = response.ok ? await response.json() : [];

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Organizations</h1>
        <p className="text-sm text-muted-foreground">
          Create an organization, then add audit periods to it.
        </p>
      </div>

      <form action={createOrganization} className="flex gap-2">
        <input
          name="name"
          required
          placeholder="Organization name"
          className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        />
        <button
          type="submit"
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
        >
          Create
        </button>
      </form>

      <ul className="divide-y divide-border rounded-md border border-border">
        {organizations.map((org) => (
          <li key={org.id}>
            <Link
              href={`/organizations/${org.id}`}
              className="block px-4 py-3 text-sm text-foreground hover:bg-muted"
            >
              {org.name}
            </Link>
          </li>
        ))}
        {organizations.length === 0 && (
          <li className="px-4 py-3 text-sm text-muted-foreground">No organizations yet.</li>
        )}
      </ul>
    </div>
  );
}
