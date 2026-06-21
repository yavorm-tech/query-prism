import { Navigate, Outlet } from "react-router-dom";
import { Spinner } from "flowbite-react";
import { useAuth } from "../../lib/auth-context";

export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
