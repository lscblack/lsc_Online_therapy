import { apiFetch } from "./client";
import { setTokens } from "../auth/tokenStore";
import type { AuditEntry, Document, ReviewStatus, TokenPair, User } from "./types";

const A = { auth: "admin" } as const;

export const admin = {
  /** Log in and store the ADMIN token pair (separate from the end-user pair). */
  async login(email: string, password: string): Promise<TokenPair> {
    const t = await apiFetch<TokenPair>("/v1/admin/login", { method: "POST", auth: "none", body: { email, password } });
    setTokens("admin", t);
    return t;
  },
  listDocuments: () => apiFetch<Document[]>("/v1/admin/documents", A),
  /** form fields: title, file, language?, topic_tags? */
  uploadDocument: (form: FormData) => apiFetch<Document>("/v1/admin/documents", { ...A, method: "POST", body: form }),
  reviewDocument: (id: string, status: ReviewStatus, notes?: string) =>
    apiFetch<Document>(`/v1/admin/documents/${encodeURIComponent(id)}/review`, { ...A, method: "POST", body: { status, notes: notes ?? null } }),
  reindexDocument: (id: string) =>
    apiFetch<Document>(`/v1/admin/documents/${encodeURIComponent(id)}/reindex`, { ...A, method: "POST" }),
  deleteDocument: (id: string) =>
    apiFetch<void>(`/v1/admin/documents/${encodeURIComponent(id)}`, { ...A, method: "DELETE" }),
  listUsers: () => apiFetch<User[]>("/v1/admin/users", A),
  disableUser: (id: string) =>
    apiFetch<User>(`/v1/admin/users/${encodeURIComponent(id)}/disable`, { ...A, method: "POST" }),
  listAudit: () => apiFetch<AuditEntry[]>("/v1/admin/audit", A),
};
