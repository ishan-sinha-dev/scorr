"use server";

import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";

export async function createOrganization(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return;

  const response = await apiFetch("/organizations", {
    method: "POST",
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create organization (${response.status})`);
  }

  revalidatePath("/organizations");
}
