import { useForm } from "@tanstack/react-form";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, Label, TextInput, Alert, Card } from "flowbite-react";
import { forgotPassword } from "../lib/api/auth";

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { email: "" },
    onSubmit: async ({ value }) => {
      try {
        await forgotPassword(value.email);
        setSubmittedEmail(value.email);
        setSubmitted(true);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      }
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface">
      <Card className="w-full max-w-md">
        <h1 className="text-xl font-semibold">Forgot password?</h1>
        <p className="text-text-dim text-sm">
          Enter your email and we'll send a reset link
        </p>
        {submitted ? (
          <div className="text-center space-y-3 py-2">
            <p className="text-sm font-medium text-text">Check your inbox</p>
            <p className="text-xs text-text-dim">
              If <span className="text-text">{submittedEmail}</span> is
              registered, you'll receive a reset link shortly. Check your spam
              folder if it doesn't arrive.
            </p>
            <Link to="/login" className="block mt-4 text-xs text-accent hover:underline">
              Back to sign in
            </Link>
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
              <form.Field name="email">
                {(f) => (
                  <div>
                    <Label htmlFor="email" value="Email address" />
                    <TextInput
                      id="email"
                      type="email"
                      placeholder="you@company.com"
                      value={f.state.value}
                      onChange={(e) => f.handleChange(e.target.value)}
                      required
                    />
                  </div>
                )}
              </form.Field>
              <form.Subscribe selector={(s) => s.isSubmitting}>
                {(isSubmitting) => (
                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? "Sending…" : "Send reset link"}
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
