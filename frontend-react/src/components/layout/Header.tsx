import { Link, NavLink } from "react-router-dom";
import UserMenu from "./UserMenu";

const navLinks = [
  { to: "/topics", label: "Topics" },
  { to: "/settings/company", label: "Company Settings" },
  { to: "/pricing", label: "Billing" },
];

export default function Header() {
  return (
    <header className="h-[10vh] px-6 flex items-center justify-between border-b border-border bg-panel">
      <Link to="/" className="text-xl font-bold tracking-tight">
        <span style={{ color: "#FF3B3B" }}>Q</span>
        <span style={{ color: "#FF7A1A" }}>u</span>
        <span style={{ color: "#FFD600" }}>e</span>
        <span style={{ color: "#4ADE80" }}>r</span>
        <span style={{ color: "#22D3EE" }}>y</span>
        <span style={{ color: "#4F8EF7" }}>P</span>
        <span style={{ color: "#6366F1" }}>r</span>
        <span style={{ color: "#A855F7" }}>i</span>
        <span style={{ color: "#EC4899" }}>s</span>
        <span style={{ color: "#F43F5E" }}>m</span>
      </Link>
      <nav className="flex items-center gap-6">
        {navLinks.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `text-sm font-medium transition-colors hover:text-accent ${isActive ? "text-accent" : "text-text-dim"}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <UserMenu />
    </header>
  );
}
