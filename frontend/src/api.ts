const API = (import.meta as any).env.VITE_API_URL || "http://localhost:8000";
let token = sessionStorage.getItem("elv_token") || "";
export const getToken = () => token;
export const setToken = (t: string) => { token = t; t ? sessionStorage.setItem("elv_token", t) : sessionStorage.removeItem("elv_token"); };
const headers = () => ({ "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) });
async function fail(res: Response): Promise<never> { const e = await res.json().catch(() => ({})); throw new Error(typeof e.detail === "string" ? e.detail : "Check the details you entered and try again."); }
export async function api(path: string, opts: any = {}) {
  const res = await fetch(API + path, { method: opts.method, headers: headers(), body: opts.body ? JSON.stringify(opts.body) : undefined });
  if (!res.ok) await fail(res);
  return res.json();
}
export async function download(path: string, name: string) {
  const res = await fetch(API + path, { headers: headers() });
  if (!res.ok) await fail(res);
  const a = document.createElement("a"); a.href = URL.createObjectURL(await res.blob()); a.download = name; a.click(); URL.revokeObjectURL(a.href);
}
