import { Dropdown } from "flowbite-react";
import { Settings } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth-context";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) return null;
  const initials = (user.username || "?").slice(0, 2).toUpperCase();

  return (
    <Dropdown
      arrowIcon={false}
      inline
      label={
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full overflow-hidden border border-border shrink-0">
            {user.avatar ? (
              <img src={user.avatar} alt={user.username} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-accent flex items-center justify-center text-white text-xs font-semibold">
                {initials}
              </div>
            )}
          </div>
          <div className="text-left leading-tight">
            <div className="text-sm font-medium">{user.username}</div>
            <div className="text-xs text-text-dim">{user.email}</div>
          </div>
          <Settings className="h-5 w-5 text-text-dim" />
        </div>
      }
    >
      <Dropdown.Item onClick={() => nav("/settings/user")}>User Settings</Dropdown.Item>
      <Dropdown.Divider />
      <Dropdown.Item onClick={logout}>Logout</Dropdown.Item>
    </Dropdown>
  );
}
