import { Route, Routes } from "react-router-dom";
import Layout from "./layout/Layout";
import { Admin, Chat } from "./pages";
import Landing from "./features/landing/Landing";
import Settings from "./features/settings/Settings";

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/admin/*" element={<Admin />} />
      </Route>
    </Routes>
  );
}
