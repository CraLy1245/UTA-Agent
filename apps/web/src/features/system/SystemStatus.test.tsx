import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemStatus } from "./SystemStatus";

function renderStatus() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SystemStatus />
    </QueryClientProvider>,
  );
}

describe("SystemStatus", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows database details after a successful health check", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          service: "Survival Agent API",
          environment: "development",
          database: {
            status: "healthy",
            engine: "sqlite",
            journal_mode: "wal",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    renderStatus();

    expect(await screen.findByText("系统已就绪")).toBeInTheDocument();
    expect(screen.getByText("后端连接正常")).toBeInTheDocument();
    expect(screen.getByText("SQLite · WAL")).toBeInTheDocument();
  });

  it("allows retrying a failed health check", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "ok",
            service: "Survival Agent API",
            environment: "development",
            database: {
              status: "healthy",
              engine: "sqlite",
              journal_mode: "wal",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    renderStatus();
    await screen.findByText("后端连接失败");
    await userEvent.click(screen.getByRole("button", { name: "重新检查" }));

    expect(await screen.findByText("后端连接正常")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
