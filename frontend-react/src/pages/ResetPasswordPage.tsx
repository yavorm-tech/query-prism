import { useForm } from "@tanstack/react-form";
import { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Button, Label, TextInput, Alert, Card } from "flowbite-react";
import { resetPassword } from "../lib/api/auth";

export default function ResetPasswordPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("Invalid or missing reset token.");
    }
  }, [token]);

  const form = useForm({
    defaultValues: { new_password: "" },
    onSubmit: async ({ value }) => {
      try {
        await resetPassword({ token, new_password: value.new_password });
        setDone(true);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      }
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface">
      <Card className="w-full max-w-md">
        <h1 className="text-xl font-semibold">Set new password</h1>
        <p className="text-text-dim text-sm">Choose a strong password for your account</p>
        {done ? (
          <div className="text-center space-y-3 py-2">
            <p className="text-sm font-medium text-text">Password updated!</p>
            <p className="text-xs text-text-dim">You can now sign in with your new password.</p>
            <Button className="w-full" onClick={() => nav("/login")}>
              Go to sign in
            </Button>
          </div>
        ) : (
          <>
            {error && <Alert color="failure">{error}</Alert>}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                form.handleSubmit();
              }}
              className="space-y-4"
            >
              <form.Field name="new_password">
                {(f) => (
                  <div>
                    <Label htmlFor="new_password" value="New password" />
                    <TextInput
                      id="new_password"
                      type="password"
                      placeholder="••••••••"
                      minLength={8}
                      value={f.state.value}
                      onChange={(e) => f.handleChange(e.target.value)}
                      required
                      disabled={!token}
                    />
                  </div>
                )}
              </form.Field>
              <form.Subscribe selector={(s) => s.isSubmitting}>
                {(isSubmitting) => (
                  <Button type="submit" className="w-full" disabled={isSubmitting || !token}>
                    {isSubmitting ? "Resetting…" : "Update password"}
                  </Button>
                )}
              </form.Subscribe>
            </form>
            <div className="text-center">
              <Link to="/login" className="text-xs text-text-dim hover:text-text">
                Back to sign in
              </Link>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
