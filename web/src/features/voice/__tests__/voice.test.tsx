import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LangProvider } from "../../../i18n/useT";
import en from "../../../i18n/en";
import type { VoiceChatResponse } from "../../../api/types";

const chatFn = vi.fn();
vi.mock("../../../api/voice", () => ({ voice: { chat: (...a: unknown[]) => chatFn(...a) } }));

import VoicePanel from "../VoicePanel";

const trackStop = vi.fn();
class FakeRecorder {
  static instances: FakeRecorder[] = [];
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  state = "inactive";
  mimeType = "audio/webm";
  constructor(public stream: unknown) { FakeRecorder.instances.push(this); }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["abc"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

function reply(over: Partial<VoiceChatResponse> = {}): VoiceChatResponse {
  return {
    transcript: "I have a headache", answer: "Rest and drink water", citations: [], safety_flags: {},
    conversation_id: "c9", language: "en", audio_base64: "aGVsbG8=", audio_mime: "audio/mpeg", tts_available: true, ...over,
  };
}
const audioPlay = vi.fn().mockResolvedValue(undefined);
const AudioCtor = vi.fn(function (this: Record<string, unknown>) { this.play = audioPlay; this.pause = vi.fn(); this.addEventListener = vi.fn(); });

function setup(props: Partial<{ conversationId: string | null; onConversationId: (id: string) => void }> = {}) {
  render(<LangProvider><VoicePanel conversationId={props.conversationId ?? null} onConversationId={props.onConversationId ?? (() => {})} /></LangProvider>);
}
async function recordAndStop() {
  fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
  const stop = await screen.findByRole("button", { name: en.voiceStop });
  fireEvent.click(stop);
}

beforeEach(() => {
  chatFn.mockReset(); trackStop.mockReset(); audioPlay.mockClear(); AudioCtor.mockClear(); FakeRecorder.instances = [];
  const stream = { getTracks: () => [{ stop: trackStop }] };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.stubGlobal("Audio", AudioCtor);
  URL.createObjectURL = vi.fn(() => "blob:x"); URL.revokeObjectURL = vi.fn();
});

describe("VoicePanel", () => {
  it("posts the recorded blob and renders transcript + answer", async () => {
    chatFn.mockResolvedValue(reply());
    const onConv = vi.fn();
    setup({ conversationId: "c1", onConversationId: onConv });
    await recordAndStop();
    expect(await screen.findByText("I have a headache")).toBeInTheDocument();
    expect(screen.getByText("Rest and drink water")).toBeInTheDocument();
    const [blob, opts] = chatFn.mock.calls[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(opts).toMatchObject({ conversation_id: "c1", language: "en" });
    expect(onConv).toHaveBeenCalledWith("c9");
  });

  it("plays reply audio when tts is available, with a replay control", async () => {
    chatFn.mockResolvedValue(reply());
    setup();
    await recordAndStop();
    await screen.findByText("Rest and drink water");
    await waitFor(() => expect(audioPlay).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: en.voiceReplay })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.voiceMute })).toBeInTheDocument();
  });

  it("does not attempt playback when tts is unavailable", async () => {
    chatFn.mockResolvedValue(reply({ tts_available: false, audio_base64: "" }));
    setup();
    await recordAndStop();
    expect(await screen.findByText("Rest and drink water")).toBeInTheDocument();
    expect(AudioCtor).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: en.voiceReplay })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders the calm crisis treatment for a crisis flag", async () => {
    chatFn.mockResolvedValue(reply({ safety_flags: { crisis: true } }));
    setup();
    await recordAndStop();
    expect(await screen.findByTestId("callout-crisis")).toBeInTheDocument();
  });

  it("shows a friendly message when mic permission is denied", async () => {
    (navigator.mediaDevices.getUserMedia as ReturnType<typeof vi.fn>).mockRejectedValue(new DOMException("no", "NotAllowedError"));
    setup();
    fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    expect(await screen.findByText(en.voiceDenied)).toBeInTheDocument();
    expect(chatFn).not.toHaveBeenCalled();
  });

  it("shows a message when the mic is unavailable", async () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    setup();
    fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    expect(await screen.findByText(en.voiceUnsupported)).toBeInTheDocument();
  });

  it("stops the mic tracks after recording", async () => {
    chatFn.mockResolvedValue(reply());
    setup();
    await recordAndStop();
    await screen.findByText("Rest and drink water");
    expect(trackStop).toHaveBeenCalled();
  });

  it("stops tracks on unmount mid-recording", async () => {
    const { unmount } = render(<LangProvider><VoicePanel conversationId={null} onConversationId={() => {}} /></LangProvider>);
    fireEvent.click(screen.getByRole("button", { name: en.voiceStart }));
    await screen.findByRole("button", { name: en.voiceStop });
    unmount();
    expect(trackStop).toHaveBeenCalled();
  });

  it("offers a live-mode tab that switches to the live panel", () => {
    setup();
    const liveTab = screen.getByRole("tab", { name: en.voiceModeLive });
    expect(liveTab).toBeEnabled();
    fireEvent.click(liveTab);
    expect(screen.getByRole("button", { name: en.voiceLiveStart })).toBeInTheDocument();
  });

  it("shows a friendly error if the voice request fails", async () => {
    chatFn.mockRejectedValue(new Error("x"));
    setup();
    await recordAndStop();
    expect(await screen.findByText(en.voiceError)).toBeInTheDocument();
  });
});
