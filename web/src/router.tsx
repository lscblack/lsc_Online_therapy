import { Route, Routes } from "react-router-dom";
import Layout from "./layout/Layout";
import { Admin, Home } from "./pages";
import Settings from "./features/settings/Settings";

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/admin/*" element={<Admin />} />
      </Route>
    </Routes>
  );
}
