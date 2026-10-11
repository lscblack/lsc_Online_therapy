import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import en from "../i18n/en";
import { API_BASE } from "../config";

describe("App shell", () => {
  beforeEach(() => localStorage.setItem("ubuzima.onboarded", "1"));
  it("renders / with app name", () => {
    render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en.appName);
  });
  it("renders /admin placeholder", () => {
    render(<MemoryRouter initialEntries={["/admin"]}><App /></MemoryRouter>);
    expect(screen.getByText(en.adminTitle)).toBeInTheDocument();
  });
  it("API base has a default", () => {
    expect(API_BASE).toMatch(/^https?:\/\//);
  });
});
