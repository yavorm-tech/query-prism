import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./auth-context";
import { MemoryRouter } from "react-router-dom";

function Probe() {
  const { user, loading } = useAuth();
  return <div>{loading ? "loading" : `user:${user ? user.username : "none"}`}</div>;
}
test("no token => no user after load", async () => {
  localStorage.clear();
  render(<MemoryRouter><AuthProvider><Probe /></AuthProvider></MemoryRouter>);
  await waitFor(() => expect(screen.getByText("user:none")).toBeInTheDocument());
});
