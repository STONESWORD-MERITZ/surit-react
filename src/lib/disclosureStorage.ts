import { supabase } from "./supabase";

export type SavedResult = {
  id: string;
  user_id: string;
  created_at: string;
  ref_date: string;
  product_type: string;
  title: string | null;
  summary_reports: Record<string, unknown>;
  meritz_easy?: unknown;
  parse_errors?: unknown;
  warnings?: unknown;
  verdict?: string | null;
  verdict_reason?: string | null;
  recommend?: string | null;
  kakao_message?: string | null;
};

export async function saveDisclosureResult(
  input: Omit<SavedResult, "id" | "user_id" | "created_at">,
): Promise<string> {
  const { data: userData, error: ue } = await supabase.auth.getUser();
  if (ue || !userData?.user) throw new Error("로그인이 필요합니다");
  const { data, error } = await supabase
    .from("disclosure_results")
    .insert([{ ...input, user_id: userData.user.id }])
    .select("id")
    .single();
  if (error) throw error;
  return (data as { id: string }).id;
}

export async function listDisclosureResults(): Promise<SavedResult[]> {
  const { data, error } = await supabase
    .from("disclosure_results")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100);
  if (error) throw error;
  return (data ?? []) as SavedResult[];
}

export async function getDisclosureResult(id: string): Promise<SavedResult | null> {
  const { data, error } = await supabase
    .from("disclosure_results")
    .select("*")
    .eq("id", id)
    .single();
  if (error) {
    if (error.code === "PGRST116") return null;
    throw error;
  }
  return data as SavedResult;
}

export async function deleteDisclosureResult(id: string): Promise<void> {
  const { error } = await supabase
    .from("disclosure_results")
    .delete()
    .eq("id", id);
  if (error) throw error;
}
