import { useForm } from "@tanstack/react-form";
import { useState, useEffect } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { Button, Label, TextInput, Alert, Card } from "flowbite-react";
import { login as apiLogin } from "../lib/api/auth";
import { refreshAccessToken } from "../lib/api/client";
import { useAuth } from "../lib/auth-context";

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const oauthSuccess = params.get("oauth") === "success";
  const oauthError = params.get("error");
  const [error, setError] = useState<string | null>(
    oauthError === "oauth_cancelled"
      ? "Google sign-in was cancelled."
      : oauthError
      ? "Google sign-in failed. Please try again."
      : null
  );

  // Back from Google: the session is in the refresh cookie; exchange it for an access token.
  useEffect(() => {
    if (!oauthSuccess) return;
    refreshAccessToken().then((token) => {
      if (token) login(token).then(() => nav("/"));
      else setError("Google sign-in failed. Please try again.");
    });
  }, [oauthSuccess, login, nav]);

  const form = useForm({
    defaultValues: { email: "", password: "" },
    onSubmit: async ({ value }) => {
      try {
        const { access_token } = await apiLogin(value);
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
        <h1 className="text-xl font-semibold">Sign in to QueryPrism</h1>
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
                <Label htmlFor="email" value="Email" />
                <TextInput
                  id="email"
                  type="email"
                  value={f.state.value}
                  onChange={(e) => f.handleChange(e.target.value)}
                  required
                />
              </div>
            )}
          </form.Field>
          <form.Field name="password">
            {(f) => (
              <div>
                <Label htmlFor="password" value="Password" />
                <TextInput
                  id="password"
                  type="password"
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
                {isSubmitting ? "Signing in…" : "Sign in"}
              </Button>
            )}
          </form.Subscribe>
        </form>
        <a href={`${import.meta.env.VITE_API_URL}/auth/oauth/google`}>
          <Button color="light" className="w-full">
            Continue with Google
          </Button>
        </a>
        <div className="flex justify-between text-sm text-text-dim">
          <Link to="/register">Create account</Link>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
      </Card>
    </div>
  );
}
