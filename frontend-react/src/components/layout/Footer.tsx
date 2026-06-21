import { Link } from "react-router-dom";

export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="h-[10vh] border-t border-border bg-panel flex items-center justify-center text-xs text-text-dim gap-4">
      <span>&copy; {year} QueryPrism. All rights reserved.</span>
      <Link to="/privacy" className="hover:underline">
        Privacy
      </Link>
      <Link to="/terms" className="hover:underline">
        Terms
      </Link>
    </footer>
  );
}
