import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LangProvider, useT } from "../../../i18n/useT";
import en from "../../../i18n/en";
import rw from "../../../i18n/rw";

const calls: string[] = [];
const ensureAnon = vi.fn(async () => { calls.push("ensureAnon"); });
const put = vi.fn(async (_d: unknown) => { calls.push("put"); return {}; });
vi.mock("../../../auth/useAuth", () => ({ useAuth: () => ({ ensureAnon, ready: true, anonId: "a1" }) }));
vi.mock("../../../api/profile", () => ({ profile: { put: (d: unknown) => put(d) } }));

import Onboarding from "../Onboarding";
import { ONBOARDED_KEY } from "../onboarded";

function Lang() { const { lang } = useT(); return <span data-testid="lang">{lang}</span>; }
function setup(onDone = vi.fn()) {
  render(<LangProvider><Lang /><Onboarding onDone={onDone} /></LangProvider>);
  return onDone;
}
const next = () => fireEvent.click(screen.getByRole("button", { name: en.obNext }));
const nick = (v: string) => fireEvent.change(screen.getByLabelText(en.obNickname), { target: { value: v } });

beforeEach(() => { calls.length = 0; ensureAnon.mockClear(); put.mockClear(); });

describe("Onboarding", () => {
  it("completes: ensureAnon then PUT with provided fields only, sets onboarded", async () => {
    const onDone = setup();
    nick("Amina"); next();
    fireEvent.change(screen.getByLabelText(en.obAge), { target: { value: "18_19" } });
    fireEvent.change(screen.getByLabelText(en.obPronouns), { target: { value: "she/her" } });
    next();
    fireEvent.click(screen.getByRole("button", { name: en.obInterestSleep }));
    fireEvent.click(screen.getByRole("button", { name: en.obToneCasual }));
    next();
    fireEvent.change(screen.getByLabelText(en.obSensitiveLabel), { target: { value: "  I have asthma " } });
    fireEvent.click(screen.getByRole("button", { name: en.obFinish }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(calls.indexOf("ensureAnon")).toBeLessThan(calls.indexOf("put"));
    expect(put).toHaveBeenCalledWith({
      nickname: "Amina", age_band: "18_19", pronouns: "she/her",
      interests: ["sleep"], tone_pref: "casual", sensitive_context: "I have asthma",
    });
    expect(localStorage.getItem(ONBOARDED_KEY)).toBe("1");
  });

  it("sensitive_context absent when left blank", async () => {
    const onDone = setup();
    nick("Amina"); next(); next(); next();
    fireEvent.click(screen.getByRole("button", { name: en.obFinish }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(put).toHaveBeenCalledWith({ nickname: "Amina" });
    expect(put.mock.calls[0][0]).not.toHaveProperty("sensitive_context");
  });

  it("skip after nickname creates session, minimal payload, marks onboarded", async () => {
    const onDone = setup();
    nick("Amina"); next();
    fireEvent.click(screen.getByRole("button", { name: en.obSkip }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(ensureAnon).toHaveBeenCalled();
    expect(put).toHaveBeenCalledWith({ nickname: "Amina" });
    expect(localStorage.getItem(ONBOARDED_KEY)).toBe("1");
  });

  it("skip with no nickname skips the profile call but still onboards", async () => {
    const onDone = setup();
    fireEvent.click(screen.getByRole("button", { name: en.obSkip }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(ensureAnon).toHaveBeenCalled();
    expect(put).not.toHaveBeenCalled();
    expect(localStorage.getItem(ONBOARDED_KEY)).toBe("1");
  });

  it("skip on the sensitive step drops the typed sensitive_context", async () => {
    const onDone = setup();
    nick("Amina"); next(); next(); next();
    fireEvent.change(screen.getByLabelText(en.obSensitiveLabel), { target: { value: "private text" } });
    fireEvent.click(screen.getByRole("button", { name: en.obSkip }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(put).toHaveBeenCalledWith({ nickname: "Amina" });
    expect(put.mock.calls[0][0]).not.toHaveProperty("sensitive_context");
  });

  it("moves focus to the step heading on step change", () => {
    setup();
    nick("Amina"); next();
    expect(screen.getByRole("heading", { level: 2 })).toHaveFocus();
  });

  it("choosing rw switches the app language", () => {
    setup();
    expect(screen.getByTestId("lang")).toHaveTextContent("en");
    fireEvent.click(screen.getByRole("radio", { name: "Kinyarwanda" }));
    expect(screen.getByTestId("lang")).toHaveTextContent("rw");
    expect(screen.getByLabelText(rw.obNickname)).toBeInTheDocument();
  });

  it("does not mark onboarded when the profile save fails", async () => {
    put.mockRejectedValueOnce(new Error("x"));
    const onDone = setup();
    nick("Amina"); next();
    fireEvent.click(screen.getByRole("button", { name: en.obSkip }));
    await screen.findByRole("alert");
    expect(onDone).not.toHaveBeenCalled();
    expect(localStorage.getItem(ONBOARDED_KEY)).toBeNull();
  });

  it("smoke at 360px: nickname field and actions render", () => {
    window.innerWidth = 360;
    setup();
    expect(screen.getByLabelText(en.obNickname)).toBeVisible();
    expect(screen.getByRole("button", { name: en.obNext })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.obSkip })).toBeInTheDocument();
  });
});
