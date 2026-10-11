import { useState } from "react";
import Onboarding from "./features/onboarding/Onboarding";
import ChatScreen from "./features/chat/ChatScreen";
import AdminPanel from "./features/admin/AdminPanel";
import { isOnboarded } from "./features/onboarding/onboarded";

export function Chat() {
  const [onboarded, setOnboarded] = useState(isOnboarded);
  if (!onboarded) return <Onboarding onDone={() => setOnboarded(true)} />;
  return <ChatScreen />;
}

export function Admin() {
  return <AdminPanel />;
}
