import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LangProvider } from "../../../i18n/useT";
import en from "../../../i18n/en";
import { ApiError } from "../../../api/client";
import type { ChatResponse } from "../../../api/types";

const streamSend = vi.fn();
const send = vi.fn();
const profileGet = vi.fn();
vi.mock("../../../api/chat", () => ({ chat: { streamSend: (...a: unknown[]) => streamSend(...a), send: (...a: unknown[]) => send(...a) } }));
vi.mock("../../../api/profile", () => ({ profile: { get: () => profileGet() } }));

import ChatScreen from "../ChatScreen";
import { ThemeProvider } from "../../../theme/ThemeProvider";

function meta(over: Partial<ChatResponse> = {}): ChatResponse {
  return { answer: "Hello there friend", citations: [], conversation_id: "c1", safety_flags: {}, language: "en", ...over };
}
function streaming(m: ChatResponse, tokens = ["Hello ", "there ", "friend"]) {
  return async (_req: unknown, onToken: (t: string) => void) => {
    for (const t of tokens) onToken(t);
    return { message: m.answer, meta: m };
  };
}
function setup() { render(<LangProvider><ThemeProvider><ChatScreen /></ThemeProvider></LangProvider>); }
async function ask(text: string) {
  fireEvent.change(screen.getByLabelText(en.chatComposerLabel), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: en.send }));
}

beforeEach(() => {
  streamSend.mockReset(); send.mockReset(); profileGet.mockReset();
  profileGet.mockResolvedValue({ nickname: "Amina" });
});

describe("ChatScreen", () => {
  it("welcomes by nickname in an empty state", async () => {
    setup();
    expect(await screen.findByText(new RegExp("Amina"))).toBeInTheDocument();
    expect(screen.getByRole("log", { name: en.chatThreadLabel })).toBeInTheDocument();
  });

  it("streams tokens into an assistant bubble with a typing indicator meanwhile", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    streamSend.mockImplementation(async (_r: unknown, onToken: (t: string) => void) => {
      onToken("Hello "); onToken("there");
      await gate;
      return { message: "Hello there friend", meta: meta() };
    });
    setup();
    await ask("hi");
    expect(await screen.findByText("hi")).toBeInTheDocument();
    expect(await screen.findByText("Hello there")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: en.chatTyping })).toBeInTheDocument();
    expect(screen.getByLabelText(en.chatComposerLabel)).toBeDisabled();
    release();
    expect(await screen.findByText("Hello there friend")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("status", { name: en.chatTyping })).toBeNull());
  });

  it("Enter sends, Shift+Enter does not", async () => {
    streamSend.mockImplementation(streaming(meta()));
    setup();
    const box = screen.getByLabelText(en.chatComposerLabel);
    fireEvent.change(box, { target: { value: "a" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(streamSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    await waitFor(() => expect(streamSend).toHaveBeenCalled());
  });

  it("renders citation chips", async () => {
    streamSend.mockImplementation(streaming(meta({ citations: [{ title: "Malaria Guide" }, { title: "ANC Handbook" }] })));
    setup();
    await ask("q");
    expect(await screen.findByText(/Malaria Guide/)).toBeInTheDocument();
    expect(screen.getByText(/ANC Handbook/)).toBeInTheDocument();
  });

  it("crisis renders a calm supportive panel, not an error", async () => {
    streamSend.mockImplementation(streaming(meta({ answer: "You are not alone. Please reach out.", safety_flags: { crisis: true } }), ["You are not alone. Please reach out."]));
    setup();
    await ask("help");
    const panel = await screen.findByTestId("callout-crisis");
    expect(panel).toHaveTextContent("You are not alone. Please reach out.");
    expect(panel).toHaveTextContent(en.chatCrisisNext);
    expect(panel.className).not.toMatch(/error|danger|red|alert/i);
    expect(panel).not.toHaveAttribute("role", "alert");
    expect(screen.queryByTestId("callout-referral")).toBeNull();
  });

  it.each([[{ needs_referral: true }], [{ in_knowledge: false }]])("referral callout for %o, not an error", async (flags) => {
    streamSend.mockImplementation(streaming(meta({ safety_flags: flags })));
    setup();
    await ask("q");
    const c = await screen.findByTestId("callout-referral");
    expect(c).toHaveTextContent(en.chatReferralTitle);
    expect(c.className).not.toMatch(/error|danger|crisis/i);
    expect(screen.queryByTestId("callout-crisis")).toBeNull();
    expect(screen.queryByTestId("chat-error")).toBeNull();
  });

  it("sends conversation_id from the first response on the second turn", async () => {
    streamSend.mockImplementation(streaming(meta({ conversation_id: "conv-9" })));
    setup();
    await ask("one");
    await screen.findByText("Hello there friend");
    await waitFor(() => expect(screen.getByLabelText(en.chatComposerLabel)).not.toBeDisabled());
    await ask("two");
    await waitFor(() => expect(streamSend).toHaveBeenCalledTimes(2));
    expect(streamSend.mock.calls[0][0].conversation_id).toBeFalsy();
    expect(streamSend.mock.calls[1][0].conversation_id).toBe("conv-9");
  });

  it("stream ApiError shows a friendly retry that re-sends", async () => {
    streamSend.mockRejectedValueOnce(new ApiError("offline", "offline", 0));
    streamSend.mockImplementation(streaming(meta()));
    setup();
    await ask("hello?");
    const err = await screen.findByTestId("chat-error");
    expect(err).toHaveTextContent(en.chatError);
    fireEvent.click(screen.getByRole("button", { name: en.chatRetry }));
    expect(await screen.findByText("Hello there friend")).toBeInTheDocument();
    expect(streamSend).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId("chat-error")).toBeNull();
  });

  it("falls back to chat.send when streaming is unavailable", async () => {
    streamSend.mockRejectedValueOnce(new ApiError("not_found", "no", 404));
    send.mockResolvedValue(meta({ answer: "Fallback answer" }));
    setup();
    await ask("q");
    expect(await screen.findByText("Fallback answer")).toBeInTheDocument();
  });
});
