import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LangProvider } from "../i18n/useT";
import { useT } from "../i18n/useT";
import en from "../i18n/en";
import rw from "../i18n/rw";
import LangToggle from "../components/LangToggle";

function Probe() {
  const { t, lang } = useT();
  return <p data-testid="p">{lang}:{t("send")}</p>;
}

describe("useT", () => {
  it("en and rw dictionaries share keys and differ", () => {
    expect(Object.keys(rw).sort()).toEqual(Object.keys(en).sort());
    expect(rw.send).not.toBe(en.send);
  });

  it("defaults to en and the toggle switches to rw, persisting", () => {
    render(<LangProvider><Probe /><LangToggle /></LangProvider>);
    expect(screen.getByTestId("p")).toHaveTextContent(`en:${en.send}`);
    fireEvent.click(screen.getByRole("button", { name: /kinyarwanda|rw/i }));
    expect(screen.getByTestId("p")).toHaveTextContent(`rw:${rw.send}`);
    expect(localStorage.getItem("ubuzima.lang")).toBe("rw");
    expect(document.documentElement.lang).toBe("rw");
  });

  it("restores persisted language", () => {
    localStorage.setItem("ubuzima.lang", "rw");
    render(<LangProvider><Probe /></LangProvider>);
    expect(screen.getByTestId("p")).toHaveTextContent(`rw:${rw.send}`);
  });
});
