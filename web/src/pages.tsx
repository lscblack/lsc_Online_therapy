import LangToggle from "./components/LangToggle";
import ThemeToggle from "./components/ThemeToggle";
import { useState } from "react";
import { useT } from "./i18n/useT";
import Onboarding from "./features/onboarding/Onboarding";
import ChatScreen from "./features/chat/ChatScreen";
import AdminPanel from "./features/admin/AdminPanel";
import { isOnboarded } from "./features/onboarding/onboarded";

export function Home() {
  const [onboarded, setOnboarded] = useState(isOnboarded);
  if (!onboarded) return <Onboarding onDone={() => setOnboarded(true)} />;
  return <ChatScreen />;
}

export function Admin() {
  const { t } = useT();
  return (
    <main className="page">
      <header className="bar">
        <h2>{t("adminTitle")}</h2>
        <div className="bar-actions"><ThemeToggle /><LangToggle /></div>
      </header>
      <AdminPanel />
    </main>
  );
}
