import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi, describe, it, expect } from "vitest";
import LoginPage from "./LoginPage";

// Mock useAuth
vi.mock("../lib/auth-context", () => ({
  useAuth: () => ({ login: vi.fn() }),
}));

// Mock the API to avoid real network calls
vi.mock("../lib/api/auth", () => ({
  login: vi.fn(),
}));

describe("LoginPage", () => {
  it("renders email field, password field, and Sign in button", () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});
