import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { RequireAuth, RequireRoles, homeFor } from "./components/Protected";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Settings from "./pages/Settings";
import DashboardResident from "./pages/DashboardResident";
import DashboardStaff from "./pages/DashboardStaff";
import DashboardAccountant from "./pages/DashboardAccountant";
import Complaints from "./pages/Complaints";
import Notices from "./pages/Notices";
import Invoices from "./pages/Invoices";
import AdminUsers from "./pages/AdminUsers";
import AdminBilling from "./pages/AdminBilling";
import AdminAccounting from "./pages/AdminAccounting";
import Reports from "./pages/Reports";

function RoleHome() {
  const raw = localStorage.getItem("smt_auth");
  const role = raw ? JSON.parse(raw)?.user?.role : null;
  return <Navigate to={homeFor(role || "RESIDENT")} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<RoleHome />} />

            <Route
              path="/dashboard"
              element={
                <RequireRoles roles={["RESIDENT"]}>
                  <DashboardResident />
                </RequireRoles>
              }
            />
            <Route
              path="/staff"
              element={
                <RequireRoles roles={["COMMITTEE", "ADMIN"]}>
                  <DashboardStaff />
                </RequireRoles>
              }
            />
            <Route
              path="/accounting-dash"
              element={
                <RequireRoles roles={["ACCOUNTANT", "ADMIN"]}>
                  <DashboardAccountant />
                </RequireRoles>
              }
            />
            <Route path="/complaints" element={<Complaints />} />
            <Route path="/notices" element={<Notices />} />
            <Route path="/settings" element={<Settings />} />
            <Route
              path="/invoices"
              element={
                <RequireRoles roles={["RESIDENT", "COMMITTEE", "ACCOUNTANT", "ADMIN"]}>
                  <Invoices />
                </RequireRoles>
              }
            />
            <Route
              path="/admin/users"
              element={
                <RequireRoles roles={["ADMIN"]}>
                  <AdminUsers />
                </RequireRoles>
              }
            />
            <Route
              path="/admin/billing"
              element={
                <RequireRoles roles={["ACCOUNTANT", "ADMIN"]}>
                  <AdminBilling />
                </RequireRoles>
              }
            />
            <Route
              path="/admin/accounting"
              element={
                <RequireRoles roles={["ACCOUNTANT", "ADMIN"]}>
                  <AdminAccounting />
                </RequireRoles>
              }
            />
            <Route
              path="/admin/reports"
              element={
                <RequireRoles roles={["ACCOUNTANT", "ADMIN"]}>
                  <Reports />
                </RequireRoles>
              }
            />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
