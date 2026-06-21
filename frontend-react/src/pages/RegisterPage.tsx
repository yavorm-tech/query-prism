import { useForm } from "@tanstack/react-form";
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button, Label, TextInput, Alert, Card } from "flowbite-react";
import { register as apiRegister } from "../lib/api/auth";
import { useAuth } from "../lib/auth-context";

export default function RegisterPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      company_name: "",
      username: "",
      email: "",
      password: "",
    },
    onSubmit: async ({ value }) => {
      try {
        const { access_token } = await apiRegister(value);
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
        <h1 className="text-xl font-semibold">Create your QueryPrism account</h1>
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
          <form.Field name="email">
            {(f) => (
              <div>
                <Label htmlFor="email" value="Email" />
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
          <form.Field name="password">
            {(f) => (
              <div>
                <Label htmlFor="password" value="Password" />
                <TextInput
                  id="password"
                  type="password"
                  placeholder="••••••••"
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
                {isSubmitting ? "Creating account…" : "Sign up"}
              </Button>
            )}
          </form.Subscribe>
        </form>
        <p className="text-xs text-text-dim text-center">
          A "General" team will be created for you. Invite teammates after signing in.
        </p>
        <div className="text-sm text-center text-text-dim">
          <Link to="/login">Already have an account? Sign in</Link>
        </div>
      </Card>
    </div>
  );
}
