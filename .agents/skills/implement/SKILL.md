---
name: implement
description: "Implement one task issue and prepare its PR handoff."
disable-model-invocation: true
---

Read the task issue, comments, and authoritative specification. State its title.
Follow `docs/agents/task-pr-handoff.md` for routing, merged prerequisites,
branching, checks, author inspection, ready-PR metadata, and completion rules.

Implement the assigned task on one branch from updated main. Use TDD at agreed
public seams where applicable. Run relevant typechecking and focused tests as
you work, and the full applicable suite at the end. Inspect your diff and test
source, fix defects, and report any unverified acceptance criteria.

Commit the task's changes. When publication is authorized, prepare the ready PR
and factory handoff described in the guide. The factory performs independent
formal review after CI; author inspection is the implementation handoff check.
Leave merge authority with the maintainer and parent acceptance with its own task.
