import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { Button, Label, TextInput, Textarea, Select, Alert, Card } from "flowbite-react";
import { Check, Mail, Loader2 } from "lucide-react";
import { sendEnterpriseContact } from "../../lib/api/contact";
import { useAuth } from "../../lib/auth-context";

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    price: "Free",
    period: "",
    model: "GPT-4o mini",
    queries: "50 / month",
    storage: "50 MB",
    teams: "1 team",
    users: "3 users",
    highlight: false,
    badge: null as string | null,
    cta: "Current free plan",
    ctaDisabled: true,
  },
  {
    id: "team",
    name: "Team",
    price: "$29",
    period: "/ month",
    model: "Claude Haiku",
    queries: "1,000 / month",
    storage: "5 GB",
    teams: "5 teams",
    users: "25 users",
    highlight: false,
    badge: null as string | null,
    cta: "Choose Team",
    ctaDisabled: false,
  },
  {
    id: "business",
    name: "Business",
    price: "$149",
    period: "/ month",
    model: "Claude Sonnet",
    queries: "5,000 / month",
    storage: "20 GB",
    teams: "Unlimited teams",
    users: "Unlimited users",
    highlight: true,
    badge: "Most popular" as string | null,
    cta: "Choose Business",
    ctaDisabled: false,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    period: "",
    model: "Claude Sonnet / Opus",
    queries: "Custom",
    storage: "Custom",
    teams: "Unlimited",
    users: "Unlimited + SSO",
    highlight: false,
    badge: null as string | null,
    cta: "Contact Sales",
    ctaDisabled: false,
  },
];

const COMPANY_SIZES = ["1–10", "11–50", "51–200", "201–1000", "1000+"];

export default function BillingPlansPanel() {
  const { user } = useAuth();
  const currentPlan = (user as { plan?: string } | null)?.plan ?? "starter";

  const [showEnterprise, setShowEnterprise] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      name: (user as { username?: string } | null)?.username ?? "",
      email: (user as { email?: string } | null)?.email ?? "",
      company_name: (user as { company_name?: string } | null)?.company_name ?? "",
      company_size: "1–10",
      message: "",
    },
    onSubmit: async ({ value }) => {
      if (!value.name.trim() || !value.email.trim() || !value.message.trim()) {
        setFormError("Name, email and message are required.");
        return;
      }
      setFormError(null);
      try {
        await sendEnterpriseContact(value);
        setSubmitted(true);
      } catch (e: unknown) {
        setFormError(e instanceof Error ? e.message : "Something went wrong");
      }
    },
  });

  const handleCta = (planId: string) => {
    if (planId === "enterprise") {
      setShowEnterprise(true);
      setSubmitted(false);
      setFormError(null);
      setTimeout(() => {
        const el = document.getElementById("enterprise-form");
        if (el && typeof el.scrollIntoView === "function") {
          el.scrollIntoView({ behavior: "smooth" });
        }
      }, 50);
    }
  };

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-text">Billing Plans</h2>
        <p className="text-xs text-text-dim">
          {user ? (
            <>
              You are on the{" "}
              <span className="text-text capitalize">{currentPlan}</span> plan
            </>
          ) : (
            "Choose the plan that fits your team"
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {PLANS.map((plan) => {
          const isCurrent = plan.id === currentPlan;
          return (
            <Card
              key={plan.id}
              className={`relative flex flex-col ${
                plan.highlight
                  ? "border-accent ring-1 ring-accent/30"
                  : isCurrent
                  ? "border-green-700/50"
                  : "border-border"
              }`}
            >
              {plan.badge && (
                <span className="absolute -top-2.5 left-4 text-[10px] font-semibold px-2 py-0.5 bg-accent text-white rounded-full">
                  {plan.badge}
                </span>
              )}
              {isCurrent && !plan.badge && (
                <span className="absolute -top-2.5 left-4 text-[10px] font-semibold px-2 py-0.5 bg-green-800 text-green-300 rounded-full">
                  Current plan
                </span>
              )}

              <div>
                <p className="text-sm font-semibold text-text">{plan.name}</p>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className="text-2xl font-bold text-text">{plan.price}</span>
                  {plan.period && (
                    <span className="text-xs text-text-dim">{plan.period}</span>
                  )}
                </div>
              </div>

              <ul className="space-y-2 flex-1">
                {[
                  { label: "Model", value: plan.model },
                  { label: "Queries", value: plan.queries },
                  { label: "Storage", value: plan.storage },
                  { label: "Teams", value: plan.teams },
                  { label: "Users", value: plan.users },
                ].map((f) => (
                  <li key={f.label} className="flex items-start gap-2 text-xs">
                    <Check size={11} className="text-accent mt-0.5 shrink-0" />
                    <span className="text-text font-medium">{f.value}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => !plan.ctaDisabled && !isCurrent && handleCta(plan.id)}
                disabled={plan.ctaDisabled || isCurrent}
                className={`w-full py-2 rounded-lg text-xs font-medium transition-colors ${
                  isCurrent
                    ? "bg-surface border border-green-700/40 text-green-400 cursor-default"
                    : plan.ctaDisabled
                    ? "bg-surface border border-border text-text-dim cursor-default"
                    : plan.highlight
                    ? "bg-accent hover:bg-blue-500 text-white"
                    : "bg-surface border border-border text-text hover:border-muted"
                }`}
              >
                {isCurrent ? "Current plan" : plan.cta}
              </button>
            </Card>
          );
        })}
      </div>

      {showEnterprise && (
        <div
          id="enterprise-form"
          className="bg-panel border border-border rounded-xl p-6 space-y-5"
        >
          <div>
            <p className="text-base font-semibold text-text">Contact Sales</p>
            <p className="text-xs text-text-dim mt-1">
              Tell us about your organisation and we'll get back to you within one business day.
            </p>
          </div>

          {submitted ? (
            <Alert color="success">
              <div className="flex items-center gap-3">
                <Check size={20} className="shrink-0" />
                <div>
                  <p className="font-medium">Thanks, we'll be in touch.</p>
                  <p className="text-sm mt-0.5">Our sales team will reach out to you shortly.</p>
                </div>
              </div>
            </Alert>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                form.handleSubmit();
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <form.Field name="name">
                  {(f) => (
                    <div>
                      <Label htmlFor="contact-name" value="Your name" />
                      <TextInput
                        id="contact-name"
                        value={f.state.value}
                        onChange={(e) => f.handleChange(e.target.value)}
                        placeholder="Jane Smith"
                      />
                    </div>
                  )}
                </form.Field>
                <form.Field name="email">
                  {(f) => (
                    <div>
                      <Label htmlFor="contact-email" value="Email" />
                      <TextInput
                        id="contact-email"
                        type="email"
                        value={f.state.value}
                        onChange={(e) => f.handleChange(e.target.value)}
                        placeholder="jane@company.com"
                      />
                    </div>
                  )}
                </form.Field>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <form.Field name="company_name">
                  {(f) => (
                    <div>
                      <Label htmlFor="contact-company" value="Company name" />
                      <TextInput
                        id="contact-company"
                        value={f.state.value}
                        onChange={(e) => f.handleChange(e.target.value)}
                        placeholder="Acme Corp"
                      />
                    </div>
                  )}
                </form.Field>
                <form.Field name="company_size">
                  {(f) => (
                    <div>
                      <Label htmlFor="contact-size" value="Company size" />
                      <Select
                        id="contact-size"
                        value={f.state.value}
                        onChange={(e) => f.handleChange(e.target.value)}
                      >
                        {COMPANY_SIZES.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </Select>
                    </div>
                  )}
                </form.Field>
              </div>

              <form.Field name="message">
                {(f) => (
                  <div>
                    <Label htmlFor="contact-message" value="Message" />
                    <Textarea
                      id="contact-message"
                      value={f.state.value}
                      onChange={(e) => f.handleChange(e.target.value)}
                      placeholder="Tell us about your use case, team size, and any specific requirements..."
                      rows={4}
                    />
                  </div>
                )}
              </form.Field>

              {formError && <Alert color="failure">{formError}</Alert>}

              <form.Subscribe selector={(s) => s.isSubmitting}>
                {(isSubmitting) => (
                  <div className="flex gap-2">
                    <Button type="submit" disabled={isSubmitting}>
                      {isSubmitting ? (
                        <Loader2 size={13} className="animate-spin mr-2" />
                      ) : (
                        <Mail size={13} className="mr-2" />
                      )}
                      {isSubmitting ? "Sending..." : "Send to sales"}
                    </Button>
                    <Button color="light" type="button" onClick={() => setShowEnterprise(false)}>
                      Cancel
                    </Button>
                  </div>
                )}
              </form.Subscribe>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
