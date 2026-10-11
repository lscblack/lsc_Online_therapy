import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LangProvider } from "../../../i18n/useT";
import { ThemeProvider } from "../../../theme/ThemeProvider";
import en from "../../../i18n/en";

const get = vi.fn();
const put = vi.fn(async (_d: unknown) => ({}));
const wipe = vi.fn(async () => undefined);
vi.mock("../../../api/profile", () => ({ profile: { get: () => get(), put: (d: unknown) => put(d), wipe: () => wipe() } }));
const ensureAnon = vi.fn(async () => {});
const auth = { ensureAnon, isAdmin: false };
vi.mock("../../../auth/useAuth", () => ({ useAuth: () => auth }));

import Settings from "../Settings";
import { ONBOARDED_KEY } from "../../onboarding/onboarded";

const PROFILE = { nickname: "Amina", age_band: "18_19", gender: null, pronouns: "she/her", tone_pref: "gentle", interests: ["sleep"], sensitive_context: null, consent: {}, updated_at: null };
function setup() {
  render(
    <LangProvider><ThemeProvider>
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes><Route path="/settings" element={<Settings />} /><Route path="/" element={<p>HOME</p>} /></Routes>
      </MemoryRouter>
    </ThemeProvider></LangProvider>,
  );
}
beforeEach(() => {
  get.mockReset().mockResolvedValue(PROFILE); put.mockClear(); wipe.mockClear();
  ensureAnon.mockClear();
  localStorage.setItem(ONBOARDED_KEY, "1");
});

describe("Settings", () => {
  it("loads current values and saves only changed fields", async () => {
    setup();
    const nick = await screen.findByLabelText(en.obNickname);
    expect(nick).toHaveValue("Amina");
    expect(screen.getByLabelText(en.obAge)).toHaveValue("18_19");
    fireEvent.change(nick, { target: { value: "Amina K" } });
    fireEvent.click(screen.getByRole("button", { name: en.setSave }));
    await screen.findByText(en.setSaved);
    expect(put).toHaveBeenCalledWith({ nickname: "Amina K" });
  });

  it("shows an error when the save fails", async () => {
    put.mockRejectedValueOnce(new Error("x"));
    setup();
    fireEvent.change(await screen.findByLabelText(en.obNickname), { target: { value: "B" } });
    fireEvent.click(screen.getByRole("button", { name: en.setSave }));
    expect(await screen.findByRole("alert")).toHaveTextContent(en.setSaveError);
  });

  it("wipe asks for confirmation, then DELETEs and clears local state", async () => {
    setup();
    await screen.findByLabelText(en.obNickname);
    fireEvent.click(screen.getByRole("button", { name: en.setWipe }));
    expect(wipe).not.toHaveBeenCalled();
    const dlg = screen.getByRole("dialog");
    fireEvent.click(within(dlg).getByRole("button", { name: en.setWipe }));
    await screen.findByText(en.setWipeDone);
    expect(wipe).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(ONBOARDED_KEY)).toBeNull();
    expect(screen.getByLabelText(en.obNickname)).toHaveValue("");
  });

  it("wipe clears the old user identity (not admin) and mints a fresh one", async () => {
    localStorage.setItem("ubuzima.tokens.user", JSON.stringify({ access_token: "a", refresh_token: "r", token_type: "bearer" }));
    localStorage.setItem("ubuzima.anon_id", "old-anon");
    localStorage.setItem("ubuzima.tokens.admin", JSON.stringify({ access_token: "x", refresh_token: "y", token_type: "bearer" }));
    setup();
    await screen.findByLabelText(en.obNickname);
    ensureAnon.mockClear();
    ensureAnon.mockImplementationOnce(async () => {
      expect(localStorage.getItem("ubuzima.tokens.user")).toBeNull();
      expect(localStorage.getItem("ubuzima.anon_id")).toBeNull();
    });
    fireEvent.click(screen.getByRole("button", { name: en.setWipe }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: en.setWipe }));
    await screen.findByText(en.setWipeDone);
    expect(wipe).toHaveBeenCalledTimes(1);
    expect(ensureAnon).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem("ubuzima.tokens.admin")).not.toBeNull();
  });

  it("cancelling the wipe dialog does nothing", async () => {
    setup();
    await screen.findByLabelText(en.obNickname);
    fireEvent.click(screen.getByRole("button", { name: en.setWipe }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: en.adminCancel }));
    expect(wipe).not.toHaveBeenCalled();
    expect(localStorage.getItem(ONBOARDED_KEY)).toBe("1");
  });

  it("re-run onboarding resets the flag and goes home", async () => {
    setup();
    fireEvent.click(await screen.findByRole("button", { name: en.setRerun }));
    expect(localStorage.getItem(ONBOARDED_KEY)).toBeNull();
    expect(await screen.findByText("HOME")).toBeInTheDocument();
  });

  it("theme and language toggles persist", async () => {
    setup();
    await screen.findByLabelText(en.obNickname);
    fireEvent.click(screen.getByRole("button", { name: /Theme/ }));
    expect(localStorage.getItem("ubuzima.theme")).toMatch(/light|dark/);
    fireEvent.click(screen.getByRole("button", { name: /Language/ }));
    await waitFor(() => expect(localStorage.getItem("ubuzima.lang")).toBe("rw"));
  });
});
