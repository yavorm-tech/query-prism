import React from "react";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { AuthProvider } from "./lib/auth-context";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import AppLayout from "./components/layout/AppLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import OnboardingPage from "./pages/OnboardingPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import TopicsPage from "./pages/TopicsPage";
import TopicDetailPage from "./pages/TopicDetailPage";
import UserSettingsPage from "./pages/UserSettingsPage";
import CompanySettingsPage from "./pages/CompanySettingsPage";
import PricingPage from "./pages/PricingPage";
import PrivacyPage from "./pages/PrivacyPage";
import TermsPage from "./pages/TermsPage";

function withAuth(children: React.ReactNode) {
  return <AuthProvider>{children}</AuthProvider>;
}

const router = createBrowserRouter([
  { path: "/privacy", element: <PrivacyPage /> },
  { path: "/terms", element: <TermsPage /> },
  { path: "/login", element: withAuth(<LoginPage />) },
  { path: "/register", element: withAuth(<RegisterPage />) },
  { path: "/onboarding", element: withAuth(<OnboardingPage />) },
  { path: "/forgot-password", element: withAuth(<ForgotPasswordPage />) },
  { path: "/reset-password", element: withAuth(<ResetPasswordPage />) },
  {
    element: withAuth(<ProtectedRoute />),
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <Navigate to="/topics" replace /> },
          { path: "/topics", element: <TopicsPage /> },
          { path: "/topics/:id", element: <TopicDetailPage /> },
          { path: "/settings/user", element: <UserSettingsPage /> },
          { path: "/settings/company", element: <CompanySettingsPage /> },
          { path: "/pricing", element: <PricingPage /> },
        ],
      },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
