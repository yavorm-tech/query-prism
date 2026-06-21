import { useState } from "react";
import { useAuth } from "../../lib/auth-context";
import { forgotPassword } from "../../lib/api/auth";
import AvatarPicker from "./AvatarPicker";

export default function AccountPanel() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  const initials = (user.username || "?").slice(0, 2).toUpperCase();

  async function handleChangePassword() {
    if (sending || sent) return;
    setSending(true);
    setError(null);
    try {
      await forgotPassword(user!.email);
      setSent(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="p-6 space-y-8">
      <section>
        <h2 className="text-base font-semibold mb-4">Profile picture</h2>
        <AvatarPicker initials={initials} />
      </section>

      <hr className="border-border" />

      <section>
        <h2 className="text-base font-semibold mb-1">Account info</h2>
        <div className="space-y-2 text-sm">
          <div>
            <span className="text-text-dim">Username: </span>
            <span className="font-medium">{user.username}</span>
          </div>
          <div>
            <span className="text-text-dim">Email: </span>
            <span className="font-medium">{user.email}</span>
          </div>
        </div>
      </section>

      <hr className="border-border" />

      <section>
        <h2 className="text-base font-semibold mb-2">Change password</h2>
        <p className="text-sm text-text-dim mb-3">
          We&apos;ll send a password reset link to <strong>{user.email}</strong>.
        </p>
        {sent ? (
          <p className="text-sm text-green-500" role="status">
            We&apos;ve emailed you a reset link.
          </p>
        ) : (
          <button
            type="button"
            onClick={handleChangePassword}
            disabled={sending}
            className="px-4 py-2 rounded-lg border border-border bg-panel text-sm font-medium hover:border-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "Sending…" : "Send reset link"}
          </button>
        )}
        {error && (
          <p className="text-sm text-red-500 mt-2" role="alert">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}
