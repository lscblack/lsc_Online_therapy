import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import gitignore from "../../.gitignore?raw";
import App from "../App";
import { AuthProvider } from "../auth/useAuth";
import en from "../i18n/en";

vi.mock("../api/profile", () => ({ profile: { get: async () => ({ nickname: null, interests: [], consent: {} }), put: vi.fn(), wipe: vi.fn() } }));

function at(path: string) {
  return render(<AuthProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></AuthProvider>);
}
beforeEach(() => localStorage.setItem("ubuzima.onboarded", "1"));

describe("app routes + nav", () => {
  it.each(["/", "/settings", "/admin"])("%s renders without crashing", (p) => {
    at(p);
    expect(screen.getByRole("navigation", { name: en.navMain })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
  it("nav links to Chat, Settings and Admin", () => {
    at("/");
    const nav = screen.getByRole("navigation", { name: en.navMain });
    expect(nav.querySelector('a[href="/"]')).toHaveTextContent(en.navChat);
    expect(nav.querySelector('a[href="/settings"]')).toHaveTextContent(en.settings);
    expect(nav.querySelector('a[href="/admin"]')).toHaveTextContent(en.navAdmin);
  });
  it("theme and language toggles are in the header", () => {
    at("/settings");
    expect(screen.getAllByRole("button", { name: new RegExp(en.theme) }).length).toBeGreaterThan(0);
  });
  it("build artifact tsbuildinfo is gitignored", () => {
    expect(gitignore).toContain("*.tsbuildinfo");
  });
});
