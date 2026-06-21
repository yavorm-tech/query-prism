import { useForm } from "@tanstack/react-form";
import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Label, TextInput, Alert, Card } from "flowbite-react";
import { completeOAuth } from "../lib/api/auth";
import { useAuth } from "../lib/auth-context";

export default function OnboardingPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const pendingToken = params.get("token") || "";
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pendingToken) {
      nav("/login");
      return;
    }
    // Decode the JWT payload (no verification — just read the claims)
    try {
      const payload = JSON.parse(atob(pendingToken.split(".")[1]));
      if (payload.type !== "oauth_pending") {
        nav("/login");
        return;
      }
      setEmail(payload.email || "");
    } catch {
      nav("/login");
    }
  }, [pendingToken, nav]);

  const form = useForm({
    defaultValues: {
      company_name: "",
      username: "",
    },
    onSubmit: async ({ value }) => {
      try {
        const { access_token } = await completeOAuth({
          pending_token: pendingToken,
          company_name: value.company_name,
          username: value.username,
        });
        await login(access_token);
        nav("/");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      }
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface">
      <Card className="w-full max-w-md">
        <h1 className="text-xl font-semibold">Almost there</h1>
        <p className="text-text-dim text-sm">Set up your account to continue</p>
        {email && (
          <div className="bg-accent-dim border border-accent/30 rounded-lg px-3 py-2.5 text-sm">
            <p className="text-xs text-text-dim">Signing in as</p>
            <p className="text-accent font-medium">{email}</p>
          </div>
        )}
        {error && <Alert color="failure">{error}</Alert>}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            form.handleSubmit();
          }}
          className="space-y-4"
        >
          <form.Field name="company_name">
            {(f) => (
              <div>
                <Label htmlFor="company_name" value="Company name" />
                <TextInput
                  id="company_name"
                  type="text"
                  placeholder="Acme Corp"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  required
                  autoFocus
                />
              </div>
            )}
          </form.Field>
          <form.Field name="username">
            {(f) => (
              <div>
                <Label htmlFor="username" value="Username" />
                <TextInput
                  id="username"
                  type="text"
                  placeholder="your_username"
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
                {isSubmitting ? "Finishing…" : "Create account"}
              </Button>
            )}
          </form.Subscribe>
        </form>
        <p className="text-xs text-text-dim text-center">
          A "General" team will be created for you automatically.
        </p>
      </Card>
    </div>
  );
}
