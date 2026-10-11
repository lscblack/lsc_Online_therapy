import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import { AuthProvider } from "../auth/useAuth";
import en from "../i18n/en";
import { API_BASE } from "../config";

describe("App shell", () => {
  beforeEach(() => localStorage.setItem("ubuzima.onboarded", "1"));
  it("renders / landing with brand + a hero heading", () => {
    render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText(en.appName).length).toBeGreaterThan(0);
  });
  it("renders /admin login", () => {
    render(<AuthProvider><MemoryRouter initialEntries={["/admin"]}><App /></MemoryRouter></AuthProvider>);
    expect(screen.getByText(en.adminSignIn)).toBeInTheDocument();
    expect(screen.getByLabelText(en.adminPassword)).toBeInTheDocument();
  });
  it("API base has a default", () => {
    expect(API_BASE).toMatch(/^https?:\/\//);
  });
});
