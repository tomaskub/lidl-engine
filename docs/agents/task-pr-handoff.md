# Task PR handoff

## Start one implementation task

Read the task, relevant comments, authoritative specification, and native Linear
blocking relationships. Require explicit repository routing to
`tomaskub/lidl-engine`, profile `lidl-engine`, target `main`, and team `PER`.
The delivery project must be allowed by the trusted installed profile. A project
or parent alone never selects this repository. Specification containers are
context, not executable tasks, even when labeled `ready-for-agent`.

Use one implementation issue, one task branch, and one PR to `main`. For each
blocker, verify its prerequisite PR merged into `main`; a Done label alone is
insufficient. Fetch updated `origin/main` and start the task from that revision.
Preserve existing branches and worktrees. Independent tasks may start separately
from main. Dependent tasks wait for merged prerequisites rather than borrowing
unmerged changes from another task branch.

An integration exception requires maintainer-approved issue scope, prerequisites,
and an explicit completion target. The current controller accepts exactly one
implementation issue per PR. Keep a multi-issue exception outside automatic
enrollment until supported. Merging into an integration branch never completes
the issues' delivery to main.

## Prepare a ready PR

Implement only the assigned task criteria and relevant shared specification
constraints. Preserve existing local checks and inspect the complete diff,
untracked files, and supporting test source. Run the checks in `ci/README.md`
and any application checks applicable to the task. Report failures and missing
verification truthfully. Author inspection does not produce a formal verdict.
The implementing agent hands off without a duplicate mandatory formal review.
The factory runs independent Standards and Spec reviews after matching CI.

When publication is authorized, prepare a PR to `main` from an approved author's
branch inside this repository. Keep incomplete work draft. Include a concise
scope description, acceptance evidence, limitations, and separately tracked
launch obligations. Use exactly one of each field on its own line:

```text
Factory-Issue: PER-56
Factory-Profile: lidl-engine
Factory-Spec: linear:issue:PER-41
```

These values are the concrete PER-56 example. Substitute the actual implementation
issue and authoritative source for another task. A project document uses
`Factory-Spec: linear:project-document:<document-id>`. The issue must explicitly
identify that same source, have the `lidl-engine` Repository label, and resolve
as an implementation issue in the allowed tracker scope. Incidental links and
closing keywords cannot replace these fields or claim parent ownership.

Apply the GitHub PR label `factory` and mark the PR ready only after checks and
author inspection. Read back the body, label, head repository, head revision,
and base branch. The ready PR is the enrollment handoff. Do not publish a passing
factory verdict, merge, or mark the issue Done as part of implementation.
After enrollment, the controller owns repair commits, pushes, GitHub publications,
and Linear writes. Reviewers have read-only access; repair workers edit only
the assigned repair worktree. Enforce those boundaries through permissions and
credentials as well as worker instructions.

## Completion and evidence

Task completion follows a verified merge into main and recorded merge/evidence
links. Only the explicitly owned implementation issue completes. Parent feature
acceptance requires its own final acceptance task after the required slices
merge. Launch obligations remain separate and visible in the PR summary.
Neither a child merge nor passing baseline CI completes a parent or launch task.
PER-25 and its existing work remain outside PER-56's ownership.

The normalized Linear adapter must retain task criteria, shared constraints,
and requirements assigned to other issues as separate context. Ambiguous source
references, roles, or assignments block review rather than expanding ownership.
Configure authenticated adapters and the trusted requirements manifest before
live enrollment. The client example does not establish unattended access.

## Client settings and CI selectors

`factory.toml` records client-owned routing, standards, source kinds, and current
CI selectors. Application code, checks, and evidence production stay in this
repository. Install and run the controller from `tomaskub/local-pr-factory`.
The maintainer promotes reviewed settings into its trusted installed policy;
never load proposed PR settings as the authority for that PR's review.

The bootstrap factory profile used planned selectors `PR validation` and
`factory-ci-evidence`. The merged PER-45 producer instead uses `CI evidence`,
workflow path `.github/workflows/ci-evidence.yml`, verification job `verify`,
and final artifact `ci-evidence-<run_id>-<run_attempt>`. Resolve the placeholders
to the selected run and attempt. `ci-raw-*` is intermediate and cannot support
review. Preserve all revision, execution, expiration, and publisher checks in
`ci/README.md`. Updating trusted selector consumption belongs to the controller;
this change neither activates gates nor claims its consumer is implemented.

The approved Factory v1 project UUID is in `factory.toml`. Other delivery
projects, including the application's `Lidl-engine` project, require explicit
allowlisting in trusted policy before automatic enrollment. Never move a task
between projects merely to satisfy enrollment.

For local routing validation, use the installed controller's `factory status`
with this configuration, profile/repository-label `lidl-engine`, repository
`tomaskub/lidl-engine`, team `PER`, and the configured project UUID. This validates
configuration only. It does not approve PR-supplied policy for live use.
See `../factory-handoff-verification.md` for the walkthrough and executable
scripted enrollment check.
