import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

test("redirects to login when unauthenticated", async () => {
  localStorage.clear();
  window.history.pushState({}, "", "/");
  render(<App />);
  await waitFor(() => expect(screen.getByText(/Sign in to QueryPrism/i)).toBeInTheDocument());
});
