import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import AppShell from "./components/layout/AppShell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ReviewPage from "./pages/ReviewPage";
import AuditPage from "./pages/AuditPage";

function ProtectedRoute({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
