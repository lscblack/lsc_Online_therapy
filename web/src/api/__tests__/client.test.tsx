import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { API_BASE } from "../../config";
import { ApiError, apiFetch } from "../client";
import { parseSSE } from "../sse";
import { chat } from "../chat";
import { admin } from "../admin";
import { identity } from "../identity";
import { clearTokens, getAnonId, getTokens, setTokens } from "../../auth/tokenStore";
import { StrictMode } from "react";
import { AuthProvider, useAuth } from "../../auth/useAuth";

const U = (p: string) => `${API_BASE}${p}`;
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const pair = (n: string) => ({ access_token: `a-${n}`, refresh_token: `r-${n}`, token_type: "bearer" });

describe("apiFetch", () => {
  it("attaches the bearer token (user default, admin on request)", async () => {
    setTokens("user", pair("u")); setTokens("admin", pair("ad"));
    const seen: (string | null)[] = [];
    server.use(http.get(U("/v1/x"), ({ request }) => { seen.push(request.headers.get("authorization")); return HttpResponse.json({ ok: 1 }); }));
    await apiFetch("/v1/x");
    await apiFetch("/v1/x", { auth: "admin" });
    await apiFetch("/v1/x", { auth: "none" });
    expect(seen).toEqual(["Bearer a-u", "Bearer a-ad", null]);
  });

  it("parses the error envelope into ApiError", async () => {
    server.use(http.get(U("/v1/x"), () => HttpResponse.json({ error: { code: "forbidden", message: "nope" } }, { status: 403 })));
    const e = await apiFetch("/v1/x").catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ code: "forbidden", message: "nope", status: 403 });
  });

  it("on 401 refreshes once then retries", async () => {
    setTokens("user", pair("old"));
    let calls = 0, refreshes = 0;
    server.use(
      http.post(U("/v1/identity/refresh"), async ({ request }) => {
        refreshes++;
        expect(await request.json()).toEqual({ refresh_token: "r-old" });
        return HttpResponse.json(pair("new"));
      }),
      http.get(U("/v1/x"), ({ request }) => {
        calls++;
        return request.headers.get("authorization") === "Bearer a-new"
          ? HttpResponse.json({ ok: true })
          : HttpResponse.json({ error: { code: "unauthorized", message: "x" } }, { status: 401 });
      }),
    );
    expect(await apiFetch("/v1/x")).toEqual({ ok: true });
    expect(refreshes).toBe(1); expect(calls).toBe(2);
    expect(getTokens("user")?.access_token).toBe("a-new");
  });

  it("refresh failure clears tokens and throws an auth error", async () => {
    setTokens("user", pair("old"));
    server.use(
      http.post(U("/v1/identity/refresh"), () => HttpResponse.json({ error: { code: "unauthorized", message: "bad" } }, { status: 401 })),
      http.get(U("/v1/x"), () => HttpResponse.json({ error: { code: "unauthorized", message: "x" } }, { status: 401 })),
    );
    const e = await apiFetch("/v1/x").catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect((e as ApiError).code).toBe("auth_expired");
    expect((e as ApiError).status).toBe(401);
    expect(getTokens("user")).toBeNull();
  });

  it("network failure throws ApiError('offline')", async () => {
    server.use(http.get(U("/v1/x"), () => HttpResponse.error()));
    const e = await apiFetch("/v1/x").catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ code: "offline", status: 0 });
  });
});

describe("refresh robustness", () => {
  const unauth = () => HttpResponse.json({ error: { code: "unauthorized", message: "x" } }, { status: 401 });
  it("transient refresh failures (offline, 5xx, malformed) keep tokens", async () => {
    for (const refresh of [() => HttpResponse.error(), () => new HttpResponse("boom", { status: 503 }), () => HttpResponse.json({ foo: 1 })]) {
      setTokens("user", pair("old"));
      server.use(http.post(U("/v1/identity/refresh"), refresh), http.get(U("/v1/x"), unauth));
      const e = await apiFetch("/v1/x").catch((x: unknown) => x);
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).code).not.toBe("auth_expired");
      expect(getTokens("user")?.access_token).toBe("a-old");
    }
  });
  it("definitive 403 refresh clears tokens", async () => {
    setTokens("user", pair("old"));
    server.use(http.post(U("/v1/identity/refresh"), () => HttpResponse.json({ error: { code: "forbidden", message: "x" } }, { status: 403 })), http.get(U("/v1/x"), unauth));
    await expect(apiFetch("/v1/x")).rejects.toMatchObject({ code: "auth_expired" });
    expect(getTokens("user")).toBeNull();
  });
  it("non-JSON 2xx throws typed ApiError", async () => {
    server.use(http.get(U("/v1/x"), () => new HttpResponse("<html>", { status: 200 })));
    await expect(apiFetch("/v1/x")).rejects.toMatchObject({ code: "bad_response" });
  });
});

describe("tokenStore", () => {
  it("keeps user and admin pairs separate", () => {
    setTokens("user", pair("u")); setTokens("admin", pair("a"));
    expect(getTokens("user")?.access_token).toBe("a-u");
    expect(getTokens("admin")?.access_token).toBe("a-a");
    clearTokens("admin");
    expect(getTokens("admin")).toBeNull();
    expect(getTokens("user")?.access_token).toBe("a-u");
  });
});

describe("auth", () => {
  const wrap = ({ children }: { children: ReactNode }) => <AuthProvider>{children}</AuthProvider>;

  it("ensureAnon bootstraps and stores the user token", async () => {
    server.use(http.post(U("/v1/identity/anon"), () => HttpResponse.json({ ...pair("anon"), anon_id: "z1" })));
    const { result } = renderHook(() => useAuth(), { wrapper: wrap });
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.anon).toBe(true);
    expect(getTokens("user")?.access_token).toBe("a-anon");
    expect(getTokens("admin")).toBeNull();
  });

  it("StrictMode double-mount creates a single anon identity and persists anon_id", async () => {
    let n = 0;
    server.use(http.post(U("/v1/identity/anon"), async () => { n++; await new Promise((r) => setTimeout(r, 20)); return HttpResponse.json({ ...pair("s"), anon_id: "sid" }); }));
    const sw = ({ children }: { children: ReactNode }) => <StrictMode><AuthProvider>{children}</AuthProvider></StrictMode>;
    const { result } = renderHook(() => useAuth(), { wrapper: sw });
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(n).toBe(1);
    expect(result.current.anonId).toBe("sid");
    expect(getAnonId()).toBe("sid");
  });

  it("re-bootstraps anon after a definitive 401 clears the user token", async () => {
    setTokens("user", pair("old"));
    server.use(
      http.post(U("/v1/identity/refresh"), () => HttpResponse.json({}, { status: 401 })),
      http.get(U("/v1/x"), () => HttpResponse.json({}, { status: 401 })),
      http.post(U("/v1/identity/anon"), () => HttpResponse.json({ ...pair("fresh"), anon_id: "n2" })),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: wrap });
    await waitFor(() => expect(result.current.ready).toBe(true));
    await apiFetch("/v1/x").catch(() => undefined);
    await waitFor(() => expect(getTokens("user")?.access_token).toBe("a-fresh"));
    expect(result.current.anon).toBe(true);
  });

  it("adminLogin stores admin tokens separately; logout clears only admin", async () => {
    setTokens("user", pair("u"));
    server.use(
      http.post(U("/v1/admin/login"), () => HttpResponse.json(pair("adm"))),
      http.get(U("/v1/admin/users"), () => HttpResponse.json([{ id: "1", email: "a@b.c", role: "admin", is_upgraded: true, locale: "en", disabled: false, created_at: "", last_seen_at: null }])),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: wrap });
    await waitFor(() => expect(result.current.ready).toBe(true));
    await act(() => result.current.adminLogin("a@b.c", "pw"));
    expect(getTokens("admin")?.access_token).toBe("a-adm");
    expect(getTokens("user")?.access_token).toBe("a-u");
    expect(result.current.isAdmin).toBe(true);
    expect(result.current.role).toBe("admin");
    act(() => result.current.adminLogout());
    expect(getTokens("admin")).toBeNull();
    expect(getTokens("user")?.access_token).toBe("a-u");
  });
});

describe("endpoints", () => {
  it("identity.anon stores tokens; admin.login stores admin tokens", async () => {
    server.use(
      http.post(U("/v1/identity/anon"), () => HttpResponse.json({ ...pair("n"), anon_id: "q" })),
      http.post(U("/v1/admin/login"), () => HttpResponse.json(pair("m"))),
    );
    await identity.anon(); await admin.login("e@x.y", "p");
    expect(getTokens("user")?.access_token).toBe("a-n");
    expect(getTokens("admin")?.access_token).toBe("a-m");
  });
});

const streamOf = (chunks: string[]) => {
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({ start(c) { chunks.forEach((x) => c.enqueue(enc.encode(x))); c.close(); } });
};

describe("parseSSE / streamSend", () => {
  it("yields incremental events across arbitrary chunk splits and ignores [DONE]", async () => {
    const s = streamOf(["event: delta\nda", "ta: Mur", "\n\nevent: delta\ndata: ahoro\n", "\ndata: [DONE]\n\n"]);
    const out: string[] = [];
    for await (const ev of parseSSE(s)) out.push(`${ev.event}:${ev.data}`);
    expect(out).toEqual(["delta:Mur", "delta:ahoro"]);
  });

  it("handles CR split across chunks", async () => {
    const out: string[] = [];
    for await (const ev of parseSSE(streamOf(["event: delta\r\ndata: a\r", "\n\r", "\n", "data: b\n\n"]))) out.push(ev.data);
    expect(out).toEqual(["a", "b"]);
  });

  it("cancels the reader on early exit", async () => {
    let cancelled = false;
    const s = new ReadableStream<Uint8Array>({ pull(c) { c.enqueue(new TextEncoder().encode("data: x\n\n")); }, cancel() { cancelled = true; } });
    for await (const ev of parseSSE(s)) { void ev; break; }
    expect(cancelled).toBe(true);
  });

  it("streamSend surfaces an error frame as ApiError and ignores unknown events", async () => {
    server.use(http.post(U("/v1/chat/stream"), () =>
      new HttpResponse(streamOf(["event: ping\ndata: 1\n\n", "event: delta\ndata: Hi\n\n", 'event: error\ndata: {"code":"upstream","message":"LLM down"}\n\n']),
        { headers: { "Content-Type": "text/event-stream" } })));
    await expect(chat.streamSend({ message: "hi" }, () => undefined)).rejects.toMatchObject({ code: "upstream", message: "LLM down" });
  });

  it("streamSend calls onToken per delta and returns assembled message + meta", async () => {
    const meta = { answer: "Hello there", citations: [], conversation_id: "c1", safety_flags: {}, language: "en" };
    server.use(http.post(U("/v1/chat/stream"), () =>
      new HttpResponse(streamOf(["event: delta\ndata: Hello\n\n", "event: delta\ndata:  there\n\n", `event: done\ndata: ${JSON.stringify(meta)}\n\n`]),
        { headers: { "Content-Type": "text/event-stream" } })));
    setTokens("user", pair("u"));
    const toks: string[] = [];
    const r = await chat.streamSend({ message: "hi" }, (t) => toks.push(t));
    expect(toks).toEqual(["Hello", " there"]);
    expect(r.message).toBe("Hello there");
    expect(r.meta?.conversation_id).toBe("c1");
  });
});
