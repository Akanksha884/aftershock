export async function api<T = any>(path: string, o: { method?: string; json?: unknown } = {}): Promise<T> {
  const h: Record<string, string> = {};
  const t = localStorage.getItem("token");
  if (t) h.Authorization = "Bearer " + t;
  if (o.json) h["Content-Type"] = "application/json";
  const r = await fetch(path, { method: o.method, headers: h, body: o.json ? JSON.stringify(o.json) : undefined });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || r.statusText);
  return d;
}
export const COLOR: Record<string, string> = { COMPLETED: "#38D39F", WAITING_APPROVAL: "#FF9F43", MONITORING: "#55C2FF", REJECTED: "#FF4D5A", FAILED: "#FF4D5A", PROPOSED: "#626B78" };
export const label = (s: string) => s.replaceAll("_", " ");
