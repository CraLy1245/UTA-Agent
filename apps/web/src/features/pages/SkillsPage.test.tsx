import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { SkillsPage } from "./SkillsPage";

const now = "2026-07-18T12:00:00Z";
const skill = {
  id: "skill-1", name: "仓库分析", description: "可审计地分析仓库", content: "success_criteria:\n- 可追溯", status: "active", locked: false,
  use_count: 10, success_count: 8, failure_count: 2, selection_weight: 1, confidence_score: 0.75, exploration_rate: 0.1,
  stable_revision_id: "stable-1", candidate_revision_id: "candidate-1", rollback_revision_id: null, candidate_paused: false,
  consecutive_failures: 0, promotion_observation_remaining: 0, satisfaction_rate: 0.8, created_by: "worker", last_evaluated_at: now, created_at: now, updated_at: now,
};

afterEach(() => vi.restoreAllMocks());

it("shows real candidate metrics and lets the user pause deterministic trial", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes("/skills?") && !init?.method) return Response.json([skill]);
    if (url.endsWith("/skills/skill-1/evolution")) return Response.json({
      skill,
      revisions: [
        { id: "candidate-1", skill_id: "skill-1", previous_revision_id: "stable-1", operation: "create_candidate_revision", status: "candidate", name: skill.name, description: skill.description, content: skill.content, reason: "负反馈", expected_improvement: "更可靠", source_turn_ids: ["turn-1"], cognitive_job_id: "job-1", created_by: "worker", created_at: now, promoted_at: null },
        { id: "stable-1", skill_id: "skill-1", previous_revision_id: null, operation: "create", status: "stable", name: skill.name, description: skill.description, content: skill.content, reason: "重复任务", expected_improvement: null, source_turn_ids: ["turn-0"], cognitive_job_id: "job-0", created_by: "worker", created_at: now, promoted_at: null },
      ],
      usages: [
        { id: "use-1", skill_id: "skill-1", skill_revision_id: "candidate-1", turn_id: "turn-1", result: "completed", feedback: "satisfied", objective_passed: true, input_tokens: 80, output_tokens: 20, created_at: now },
      ],
      events: [],
    });
    if (url.endsWith("/skills/skill-1/candidate/candidate-1/pause") && init?.method === "POST") return Response.json({ ...skill, candidate_paused: true });
    throw new Error(`Unexpected request: ${url}`);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><SkillsPage /></QueryClientProvider>);
  expect(await screen.findByText("仓库分析")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /演化记录/ }));
  expect(await screen.findByText("1 / 5 次")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /暂停试用/ }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/candidate/candidate-1/pause"),
    expect.objectContaining({ method: "POST" }),
  ));
});
