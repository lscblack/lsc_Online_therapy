import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThemeProvider } from "../theme/ThemeProvider";
import { LangProvider } from "../i18n/useT";
import ThemeToggle from "../components/ThemeToggle";

const wrap = () =>
  render(<LangProvider><ThemeProvider><ThemeToggle /></ThemeProvider></LangProvider>);

describe("ThemeProvider", () => {
  it("applies a persisted theme to <html>", () => {
    localStorage.setItem("ubuzima.theme", "dark");
    wrap();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("toggle sets data-theme and persists", () => {
    localStorage.setItem("ubuzima.theme", "light");
    wrap();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    fireEvent.click(screen.getByRole("button"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("ubuzima.theme")).toBe("dark");
  });
});
