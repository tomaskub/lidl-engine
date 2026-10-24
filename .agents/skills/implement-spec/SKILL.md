---
name: implement-spec
description: "Implement approved spec tickets as task PRs to main."
disable-model-invocation: true
---

Read the authoritative spec, its tickets, comments, repository routes, and native
blocking relationships. Follow `docs/agents/task-pr-handoff.md` for task delivery
and completion. Treat the tickets as a graph, not a sequence of unchecked steps.

1. Find implementation tickets whose genuine prerequisites have merged to main.
   Spec containers and launch-only tasks are not implementation work.
2. Implement each eligible issue using `implement`, on its own branch and
   worktree from updated main. Independent tasks can proceed separately.
3. Prepare one PR to main per task. Preserve local checks and author inspection;
   the factory handles formal review after matching CI and the ready handoff.
4. Wait for the maintainer to merge prerequisite PRs. Fetch updated main before
   starting any newly eligible dependent task. Preserve worktrees for pending
   review or repair.
5. Verify combined behavior through the explicit final acceptance ticket after
   its prerequisites merge. Keep launch-only obligations separately tracked.
   Report task PRs and outstanding obligations without completing the parent.

Use an integration branch only for an explicitly approved exception declaring
issue scope and completion target. Current automatic enrollment supports one
implementation issue per PR; keep multi-issue exceptions on a manual route.
