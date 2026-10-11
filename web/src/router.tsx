import { Route, Routes } from "react-router-dom";
import { Admin, Home } from "./pages";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/admin/*" element={<Admin />} />
    </Routes>
  );
}
