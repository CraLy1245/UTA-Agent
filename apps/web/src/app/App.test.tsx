import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { useUiStore } from "../stores/uiStore";
import { App } from "./App";

function renderApp(path = "/chat/mock-1") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("phase 1 application shell", () => {
  beforeEach(() =>
    useUiStore.setState({
      conversationsCollapsed: false,
      statusCollapsed: false,
    }),
  );

  it("renders the three-column chat workspace and mock feedback interactions", async () => {
    const user = userEvent.setup();
    renderApp();

    expect(screen.getByText("Survival Agent")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "产品开发规划" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Agent 状态")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "满意" }));
    expect(screen.getByRole("button", { name: "满意" })).toHaveClass("active");

    await user.click(screen.getByRole("button", { name: "折叠会话栏" }));
    expect(
      screen.getByRole("button", { name: "展开会话栏" }),
    ).toBeInTheDocument();
  });

  it("opens each independent management page from the primary navigation", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("link", { name: "记忆" }));
    expect(screen.getByRole("heading", { name: "记忆" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "技能" }));
    expect(screen.getByRole("heading", { name: "技能" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "活动" }));
    expect(
      screen.getByRole("heading", { name: "后台活动" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "设置" }));
    expect(screen.getByRole("heading", { name: "设置" })).toBeInTheDocument();
  });
});
