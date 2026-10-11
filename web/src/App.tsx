import { LangProvider } from "./i18n/useT";
import AppRoutes from "./router";
import { ThemeProvider } from "./theme/ThemeProvider";

/** Providers + routes. The caller supplies the Router (BrowserRouter in main, MemoryRouter in tests). */
export default function App() {
  return (
    <LangProvider>
      <ThemeProvider>
        <AppRoutes />
      </ThemeProvider>
    </LangProvider>
  );
}
