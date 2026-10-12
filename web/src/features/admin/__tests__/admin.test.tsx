import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LangProvider } from "../../../i18n/useT";
import en from "../../../i18n/en";
import { ApiError } from "../../../api/client";

const api = vi.hoisted(() => ({
  login: vi.fn(), listDocuments: vi.fn(), uploadDocument: vi.fn(), reviewDocument: vi.fn(),
  reindexDocument: vi.fn(), me: vi.fn(), deleteDocument: vi.fn(), listUsers: vi.fn(), disableUser: vi.fn(), listAudit: vi.fn(),
  getModels: vi.fn(), providerModels: vi.fn(), setModel: vi.fn(), testModel: vi.fn(), getSystem: vi.fn(),
}));
vi.mock("../../../api/admin", () => ({ admin: api }));
vi.mock("../../../api/identity", () => ({ identity: { anon: vi.fn(async () => ({ anon_id: "a" })) } }));

import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "../../../theme/ThemeProvider";
import { AuthProvider } from "../../../auth/useAuth";
import AdminPanel from "../AdminPanel";

const doc = (o = {}) => ({
  id: "d1", title: "Sleep guide", source_filename: "s.pdf", language: "en", topic_tags: [],
  status: "indexed", review_status: "pending", review_notes: null, version: 1,
  checksum: null, created_at: "2026-01-01T00:00:00Z", indexed_at: null, ...o,
});
const user = (o = {}) => ({
  id: "u1", email: "boss@x.org", role: "admin", is_upgraded: true, locale: "en",
  disabled: false, created_at: "2026-01-01T00:00:00Z", last_seen_at: null, ...o,
});

async function loginAs(role: "admin" | "reviewer" | "fail") {
  if (role === "fail") api.me.mockRejectedValue(new ApiError("forbidden", "x", 403));
  else api.me.mockResolvedValue({ role, email: "boss@x.org" });
  api.listUsers.mockResolvedValue([user({ id: "u2", email: "other@x.org", role: "user" })]);
  render(<MemoryRouter><ThemeProvider><LangProvider><AuthProvider><AdminPanel /></AuthProvider></LangProvider></ThemeProvider></MemoryRouter>);
  fireEvent.change(screen.getByLabelText(en.adminEmail), { target: { value: "boss@x.org" } });
  fireEvent.change(screen.getByLabelText(en.adminPassword), { target: { value: "pw" } });
  fireEvent.click(screen.getByRole("button", { name: en.login }));
  await screen.findByRole("button", { name: en.logout });
  // Admins land on the Overview; navigate to Documents (the doc-centric tests expect it).
  if (role === "admin") {
    const side = screen.getByRole("navigation", { name: en.adminConsole });
    fireEvent.click(within(side).getByRole("button", { name: en.adminDocuments }));
  }
}

beforeEach(() => {
  localStorage.clear();
  Object.values(api).forEach((m) => m.mockReset());
  api.login.mockResolvedValue({});
  api.listDocuments.mockResolvedValue([doc()]);
  api.listAudit.mockResolvedValue([]);
  api.getModels.mockResolvedValue({
    active_provider: "requesty", active_model: "google/gemma-4-31b-it", is_override: false,
    providers: [
      { name: "requesty", label: "Requesty", tier: "free", note: "n", enabled: true, local: false, models: ["google/gemma-4-31b-it"] },
      { name: "ollama", label: "Ollama (local)", tier: "local", note: "n", enabled: true, local: true, models: ["llama3:latest"] },
    ],
  });
  api.providerModels.mockResolvedValue({ provider: "requesty", models: ["google/gemma-4-31b-it"] });
  api.getSystem.mockResolvedValue({ stt_provider: "whisper_local", whisper_model: "small", stt_device: "cpu", cuda_available: false, cuda_devices: 0 });
});

describe("Admin panel", () => {
  it("login success reveals the panel", async () => {
    await loginAs("admin");
    expect(api.login).toHaveBeenCalledWith("boss@x.org", "pw");
    expect(await screen.findByText("Sleep guide")).toBeInTheDocument();
  });

  it("401 on login shows invalid credentials, stays on login", async () => {
    api.login.mockRejectedValue(new ApiError("unauthorized", "no", 401));
    render(<MemoryRouter><ThemeProvider><LangProvider><AuthProvider><AdminPanel /></AuthProvider></LangProvider></ThemeProvider></MemoryRouter>);
    fireEvent.change(screen.getByLabelText(en.adminEmail), { target: { value: "a@b.c" } });
    fireEvent.change(screen.getByLabelText(en.adminPassword), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: en.login }));
    expect(await screen.findByRole("alert")).toHaveTextContent(en.adminInvalidCreds);
    expect(screen.queryByRole("button", { name: en.logout })).toBeNull();
  });

  it("upload posts multipart with title + file, then refreshes", async () => {
    await loginAs("admin");
    await screen.findByText("Sleep guide");
    api.uploadDocument.mockResolvedValue(doc({ id: "d2", title: "New" }));
    fireEvent.click(screen.getByRole("button", { name: en.adminUpload }));
    const dlg = screen.getByRole("dialog");
    fireEvent.change(within(dlg).getByLabelText(en.adminDocTitle), { target: { value: "New" } });
    const file = new File(["hello"], "n.txt", { type: "text/plain" });
    fireEvent.change(within(dlg).getByLabelText(en.adminFile), { target: { files: [file] } });
    const calls = api.listDocuments.mock.calls.length;
    fireEvent.click(within(dlg).getByRole("button", { name: en.adminUploadSubmit }));
    await waitFor(() => expect(api.uploadDocument).toHaveBeenCalled());
    const form = api.uploadDocument.mock.calls[0][0] as FormData;
    expect(form.get("title")).toBe("New");
    expect((form.get("file") as File).name).toBe("n.txt");
    await waitFor(() => expect(api.listDocuments.mock.calls.length).toBeGreaterThan(calls));
  });

  it("approve and reindex call the API", async () => {
    await loginAs("admin");
    await screen.findByText("Sleep guide");
    api.reviewDocument.mockResolvedValue(doc());
    api.reindexDocument.mockResolvedValue(doc());
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${en.adminApprove}: `) }));
    await waitFor(() => expect(api.reviewDocument).toHaveBeenCalledWith("d1", "approved", undefined));
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${en.adminReindex}`) }));
    await waitFor(() => expect(api.reindexDocument).toHaveBeenCalledWith("d1"));
  });

  it("admin sees delete (with confirm), users and audit", async () => {
    await loginAs("admin");
    await screen.findByText("Sleep guide");
    const side = screen.getByRole("navigation", { name: en.adminConsole });
    expect(within(side).getByRole("button", { name: en.adminUsers })).toBeInTheDocument();
    expect(within(side).getByRole("button", { name: en.adminAudit })).toBeInTheDocument();
    api.deleteDocument.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${en.adminDelete}`) }));
    expect(api.deleteDocument).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: en.adminConfirm }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith("d1"));
  });

  it("reviewer cannot see delete, users or audit but can review/reindex/upload", async () => {
    await loginAs("reviewer");
    await screen.findByText("Sleep guide");
    expect(screen.queryByRole("button", { name: new RegExp(`^${en.adminDelete}`) })).toBeNull();
    expect(screen.queryByRole("button", { name: en.adminUsers })).toBeNull();
    expect(screen.queryByRole("button", { name: en.adminAudit })).toBeNull();
    expect(screen.getByRole("button", { name: new RegExp(`^${en.adminApprove}: `) })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: new RegExp(`^${en.adminReindex}`) })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.adminUpload })).toBeInTheDocument();
  });

  it("unknown role (me() fails) defaults to reviewer: no admin-only UI", async () => {
    await loginAs("fail");
    await screen.findByText("Sleep guide");
    expect(screen.queryByRole("button", { name: new RegExp(en.adminDelete) })).toBeNull();
    expect(screen.queryByRole("button", { name: en.adminUsers })).toBeNull();
    expect(screen.queryByRole("button", { name: en.adminAudit })).toBeNull();
  });

  it("503 shows a clear message, no crash", async () => {
    await loginAs("admin");
    api.listDocuments.mockRejectedValue(new ApiError("unavailable", "down", 503));
    fireEvent.click(screen.getByRole("button", { name: en.adminRefresh }));
    expect(await screen.findByRole("alert")).toHaveTextContent(en.adminUnavailable);
  });

  it("403 shows not-allowed message", async () => {
    await loginAs("admin");
    api.reviewDocument.mockRejectedValue(new ApiError("forbidden", "x", 403));
    await screen.findByText("Sleep guide");
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`^${en.adminReject}: `) }));
    expect(await screen.findByRole("alert")).toHaveTextContent(en.adminForbidden);
  });
});
