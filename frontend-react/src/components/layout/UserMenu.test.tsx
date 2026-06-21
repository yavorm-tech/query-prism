import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi, describe, it, expect, beforeEach } from "vitest";
import UserMenu from "./UserMenu";

const mockLogout = vi.fn();

interface MockAuthReturn {
  user: {
    id: string;
    username: string;
    email: string;
    default_team_id: null;
  } | null;
  logout: typeof mockLogout;
  teams: [];
  activeTeamId: null;
  setActiveTeamId: ReturnType<typeof vi.fn>;
  loading: boolean;
  login: ReturnType<typeof vi.fn>;
  refreshTeams: ReturnType<typeof vi.fn>;
}

let mockAuthReturn: MockAuthReturn = {
  user: {
    id: "1",
    username: "Ann",
    email: "a@b.co",
    default_team_id: null,
  },
  logout: mockLogout,
  teams: [],
  activeTeamId: null,
  setActiveTeamId: vi.fn(),
  loading: false,
  login: vi.fn(),
  refreshTeams: vi.fn(),
};

vi.mock("../../lib/auth-context", () => ({
  useAuth: () => mockAuthReturn,
}));

describe("UserMenu", () => {
  beforeEach(() => {
    mockLogout.mockClear();
  });

  it("renders the trigger with username and email", () => {
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    );
    expect(screen.getByText("Ann")).toBeInTheDocument();
    expect(screen.getByText("a@b.co")).toBeInTheDocument();
  });

  it("shows all four menu items after clicking the trigger", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    );

    // Click the dropdown trigger using role-based query
    const trigger = screen.getByRole("button", { name: /ann/i });
    await user.click(trigger);

    expect(await screen.findByText("User Settings")).toBeInTheDocument();
    expect(await screen.findByText("Billing Plan")).toBeInTheDocument();
    expect(await screen.findByText("Company Settings")).toBeInTheDocument();
    expect(await screen.findByText("Logout")).toBeInTheDocument();
  });

  it("calls logout when Logout item is clicked", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    );

    const trigger = screen.getByRole("button", { name: /ann/i });
    await user.click(trigger);

    const logoutItem = await screen.findByText("Logout");
    await user.click(logoutItem);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when user is null", () => {
    mockAuthReturn = {
      user: null,
      logout: vi.fn(),
      teams: [],
      activeTeamId: null,
      setActiveTeamId: vi.fn(),
      loading: false,
      login: vi.fn(),
      refreshTeams: vi.fn(),
    };

    const { container } = render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    );

    expect(container.firstChild).toBeNull();
  });
});
