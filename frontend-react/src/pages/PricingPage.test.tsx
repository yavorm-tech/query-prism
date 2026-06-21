import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi, describe, it, expect, beforeEach } from "vitest";
import PricingPage from "./PricingPage";

// Mock the enterprise contact API
vi.mock("../lib/api/contact", () => ({
  sendEnterpriseContact: vi.fn(),
}));

// Mock useAuth
vi.mock("../lib/auth-context", () => ({
  useAuth: () => ({ user: null }),
}));

import { sendEnterpriseContact } from "../lib/api/contact";

const mockSendEnterpriseContact = vi.mocked(sendEnterpriseContact);

describe("PricingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders plan names", () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
    expect(screen.getByText("Enterprise")).toBeInTheDocument();
  });

  it("renders plan prices", () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("$29")).toBeInTheDocument();
    expect(screen.getByText("$149")).toBeInTheDocument();
    // "Custom" appears multiple times (price + feature items for enterprise plan)
    expect(screen.getAllByText("Custom").length).toBeGreaterThan(0);
  });

  it("shows the enterprise contact form when Contact Sales is clicked", () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /contact sales/i }));

    expect(screen.getByRole("button", { name: /send to sales/i })).toBeInTheDocument();
  });

  it("renders enterprise contact form submit button", () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /contact sales/i }));

    expect(screen.getByRole("button", { name: /send to sales/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/your name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company size/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/message/i)).toBeInTheDocument();
  });

  it("shows validation error when required fields are empty", async () => {
    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /contact sales/i }));
    fireEvent.click(screen.getByRole("button", { name: /send to sales/i }));

    await waitFor(() => {
      expect(screen.getByText(/name, email and message are required/i)).toBeInTheDocument();
    });
  });

  it("shows success message after successful submission", async () => {
    mockSendEnterpriseContact.mockResolvedValueOnce({ success: true });

    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /contact sales/i }));

    fireEvent.change(screen.getByLabelText(/your name/i), { target: { value: "Jane Smith" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: "We need enterprise features." } });

    fireEvent.click(screen.getByRole("button", { name: /send to sales/i }));

    await waitFor(() => {
      expect(screen.getByText(/thanks, we'll be in touch/i)).toBeInTheDocument();
    });

    expect(mockSendEnterpriseContact).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Jane Smith",
        email: "jane@example.com",
        message: "We need enterprise features.",
      })
    );
  });

  it("shows error message on API failure", async () => {
    mockSendEnterpriseContact.mockRejectedValueOnce(new Error("Server error"));

    render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /contact sales/i }));

    fireEvent.change(screen.getByLabelText(/your name/i), { target: { value: "Jane Smith" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: "We need enterprise features." } });

    fireEvent.click(screen.getByRole("button", { name: /send to sales/i }));

    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument();
    });
  });
});
