import { render, screen } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";
import Pagination from "./Pagination";

describe("Pagination", () => {
  const noop = vi.fn();

  it("disables First and Prev on the first page and shows page number 1", () => {
    render(
      <Pagination
        page={0}
        pageCount={3}
        onFirst={noop}
        onPrev={noop}
        onNext={noop}
        onLast={noop}
      />
    );

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /first/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /last/i })).not.toBeDisabled();
  });

  it("disables Next and Last on the last page", () => {
    render(
      <Pagination
        page={2}
        pageCount={3}
        onFirst={noop}
        onPrev={noop}
        onNext={noop}
        onLast={noop}
      />
    );

    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /first/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /prev/i })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /last/i })).toBeDisabled();
  });
});
