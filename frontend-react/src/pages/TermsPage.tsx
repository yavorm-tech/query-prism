import { Link } from "react-router-dom";

export default function TermsPage() {
  const updated = "1 June 2025";

  return (
    <div className="min-h-screen bg-surface">
      <div className="max-w-3xl mx-auto px-6 py-12 space-y-10">
        <div className="space-y-2">
          <Link to="/" className="text-xs text-text-dim hover:text-accent transition-colors">
            ← Back to QueryPrism
          </Link>
          <h1 className="text-2xl font-bold text-text mt-3">Terms of Service</h1>
          <p className="text-xs text-text-dim">Last updated: {updated}</p>
        </div>

        <Section title="1. Acceptance of Terms">
          <p>
            These Terms of Service ("Terms") constitute a legally binding agreement between you
            (and, if applicable, the organisation you represent) and QueryPrism ("we", "our",
            or "us"), governing your access to and use of the QueryPrism platform and all related
            APIs, documentation, and services (collectively, the "Service").
          </p>
          <p>
            By creating an account, clicking "I agree", or otherwise accessing the Service, you
            confirm that you have read, understood, and agree to be bound by these Terms and our{" "}
            <Link to="/privacy" className="text-accent hover:underline">Privacy Policy</Link>.
            If you do not agree, you must not use the Service.
          </p>
        </Section>

        <Section title="2. Eligibility and Accounts">
          <p>
            You must be at least 18 years old and have the legal authority to enter into these
            Terms on your own behalf or on behalf of your organisation. By registering, you
            represent that all information you provide is accurate and current.
          </p>
          <p>
            You are responsible for maintaining the confidentiality of your account credentials
            and for all activity that occurs under your account. You must notify us immediately
            at <strong>security@queryprism.com</strong> if you suspect unauthorised access.
          </p>
          <p>
            Each account is associated with a single organisation. You may not share login
            credentials across organisations or create accounts on behalf of a competitor for
            the purpose of benchmarking or reverse-engineering the Service.
          </p>
        </Section>

        <Section title="3. Subscription Plans and Billing">
          <p>
            The Service is offered under several subscription tiers (Starter, Team, Business,
            Enterprise) as described on the Billing page. Feature availability, usage limits
            (queries, storage, teams, and users), and the AI model tier are determined by your
            active plan.
          </p>
          <p>
            Paid plans are billed monthly in advance. Fees are non-refundable except as required
            by applicable law or as expressly stated in a separate written agreement. We reserve
            the right to change pricing upon 30 days' notice; continued use after the effective
            date constitutes acceptance.
          </p>
          <p>
            If payment fails, we will retry over a 7-day grace period. After the grace period,
            your account will be downgraded to the Starter (free) tier and access to paid
            features will be suspended until payment is resolved.
          </p>
        </Section>

        <Section title="4. Acceptable Use">
          <p>You agree not to use the Service to:</p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>Upload, store, or process content that is unlawful, defamatory, obscene, or infringes any third party's intellectual property rights.</li>
            <li>Transmit malware, spyware, or any malicious code.</li>
            <li>Attempt to gain unauthorised access to other tenants' data or to our infrastructure.</li>
            <li>Reverse-engineer, decompile, or disassemble any part of the Service.</li>
            <li>Use automated means to scrape, crawl, or extract data from the Service beyond normal API usage.</li>
            <li>Resell or sublicense access to the Service to third parties without our prior written consent.</li>
            <li>Violate any applicable export control or sanctions regulations.</li>
          </ul>
          <p>
            We reserve the right to suspend or terminate accounts that violate this section
            without prior notice and without refund.
          </p>
        </Section>

        <Section title="5. Intellectual Property">
          <Subsection title="5.1 Your content">
            You retain all ownership rights in the documents, data, and other content you upload
            to the Service ("Customer Content"). By uploading Customer Content you grant us a
            limited, non-exclusive, royalty-free licence to store, process, and transmit it
            solely for the purpose of providing the Service to you.
          </Subsection>
          <Subsection title="5.2 Our platform">
            QueryPrism and all underlying software, algorithms, models, interfaces, and
            documentation are and remain the exclusive property of QueryPrism. These Terms do
            not grant you any rights in our intellectual property except the limited right to
            use the Service as described herein.
          </Subsection>
          <Subsection title="5.3 Feedback">
            If you provide suggestions, ideas, or feedback about the Service ("Feedback"), you
            grant us a perpetual, irrevocable, royalty-free licence to use that Feedback without
            restriction or compensation.
          </Subsection>
        </Section>

        <Section title="6. AI-Generated Content">
          <p>
            The Service uses retrieval-augmented generation to produce answers based on your
            uploaded documents. AI-generated responses may contain inaccuracies, omissions, or
            errors. You are responsible for independently verifying any AI-generated output before
            acting on it in a professional, legal, medical, financial, or other regulated context.
          </p>
          <p>
            We make no warranty that AI-generated responses are accurate, complete, current, or
            fit for any particular purpose.
          </p>
        </Section>

        <Section title="7. Data Security and Privacy">
          <p>
            We implement technical and organisational measures designed to protect your data
            against unauthorised access, loss, or disclosure, as described in our{" "}
            <Link to="/privacy" className="text-accent hover:underline">Privacy Policy</Link>.
            However, no internet transmission or storage system is 100% secure, and we cannot
            guarantee absolute security.
          </p>
          <p>
            If you are subject to GDPR or equivalent legislation, our Data Processing Agreement
            (DPA) — available on request at <strong>legal@queryprism.com</strong> — governs the
            processing of personal data within the Service.
          </p>
        </Section>

        <Section title="8. Service Availability and SLA">
          <p>
            We target 99.5% monthly uptime for paid tiers, excluding scheduled maintenance
            windows (announced at least 48 hours in advance) and force majeure events. The
            Starter (free) tier is provided on a best-effort basis with no uptime commitment.
          </p>
          <p>
            We reserve the right to modify, suspend, or discontinue any feature of the Service
            at any time, with reasonable notice where practicable. We will not be liable for any
            modification, suspension, or discontinuance.
          </p>
        </Section>

        <Section title="9. Limitation of Liability">
          <p>
            To the maximum extent permitted by applicable law, QueryPrism and its officers,
            employees, and agents shall not be liable for any indirect, incidental, special,
            consequential, or punitive damages — including loss of profits, data, goodwill, or
            business opportunity — arising out of or related to your use of or inability to use
            the Service, regardless of the theory of liability.
          </p>
          <p>
            Our total aggregate liability for any claim arising under these Terms shall not exceed
            the greater of (a) the fees paid by you to us in the 12 months preceding the claim
            or (b) €100.
          </p>
        </Section>

        <Section title="10. Indemnification">
          <p>
            You agree to indemnify and hold harmless QueryPrism and its affiliates from any
            claims, damages, losses, and expenses (including reasonable legal fees) arising from:
            (a) your use of the Service in violation of these Terms; (b) your Customer Content;
            or (c) your violation of any third party's rights.
          </p>
        </Section>

        <Section title="11. Term and Termination">
          <p>
            These Terms remain in effect for as long as you maintain an account with us. You may
            terminate your account at any time via the Company Settings page. We may terminate or
            suspend your account immediately if you breach these Terms.
          </p>
          <p>
            Upon termination, your right to access the Service ceases immediately. We will retain
            your data for 30 days post-termination to allow for data export, after which it will
            be permanently deleted in accordance with our Privacy Policy.
          </p>
        </Section>

        <Section title="12. Governing Law and Disputes">
          <p>
            These Terms are governed by and construed in accordance with the laws of the Republic
            of Bulgaria, without regard to its conflict-of-law provisions. Any dispute arising
            out of or in connection with these Terms shall be submitted to the exclusive
            jurisdiction of the competent courts of Sofia, Bulgaria.
          </p>
          <p>
            Before initiating formal proceedings, you agree to attempt to resolve any dispute
            informally by contacting us at <strong>legal@queryprism.com</strong>. We will make
            good-faith efforts to resolve the matter within 30 days.
          </p>
        </Section>

        <Section title="13. Miscellaneous">
          <p>
            <strong>Entire agreement.</strong> These Terms, together with our Privacy Policy and
            any applicable DPA or Order Form, constitute the entire agreement between you and
            QueryPrism regarding the Service and supersede all prior agreements.
          </p>
          <p>
            <strong>Severability.</strong> If any provision of these Terms is held to be
            unenforceable, the remaining provisions will continue in full force.
          </p>
          <p>
            <strong>Waiver.</strong> Our failure to enforce any right or provision shall not
            constitute a waiver of that right or provision.
          </p>
          <p>
            <strong>Assignment.</strong> You may not assign these Terms without our prior written
            consent. We may assign our rights and obligations to an affiliate or in connection
            with a merger, acquisition, or sale of assets.
          </p>
        </Section>

        <Section title="14. Contact">
          <p>
            For any questions about these Terms, contact us at{" "}
            <strong>legal@queryprism.com</strong>.
          </p>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-text border-b border-border pb-1">{title}</h2>
      <div className="text-sm text-text-dim space-y-3 leading-relaxed">{children}</div>
    </section>
  );
}

function Subsection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold text-text">{title}</h3>
      <p>{children}</p>
    </div>
  );
}
