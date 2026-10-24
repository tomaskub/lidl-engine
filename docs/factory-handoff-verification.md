# PER-56 handoff verification

## Independent task walkthrough

For an approved implementation issue without native blockers, resolve its
explicit repository label, team, allowed delivery project, and authoritative
source. Fetch main, create one owned task branch from that revision, and
implement only that issue. Run local checks and inspect the complete diff and
test source. Prepare one same-repository PR to main with the three handoff fields
from `agents/task-pr-handoff.md`, apply `factory`, and mark ready when complete.
The factory waits for matching CI before independent review. A sibling task
neither joins this PR nor becomes owned through the shared parent reference.

The executable sample uses a scripted ready PR numbered 56 and normalized
PER-56 task/source records. Its parent has a shared merge-authority constraint
and a pilot requirement assigned to PER-57. Public status shows only PER-56
ownership and keeps the pilot criterion as other-ticket context. This exercises
enrollment, not automatic issue dispatch or a live PR numbered 56.

## Dependent task walkthrough

PER-56 declares PER-43 as a native blocker. Before implementation, the Linear
record identified `tomaskub/local-pr-factory#3` as its prerequisite PR. GitHub
reported it merged on 2026-10-23 at commit
`d929288e0d6295eb27cc5b09b567a9348215faf3`. A closed Linear issue alone was not
used as proof. The controller's public enrollment operation is available locally.

The target repository was resolved independently as `tomaskub/lidl-engine`.
Fetching its main produced `76d12e9cae0ab06a9b5957a4abfb0b34af0baf5c`, which
contains the merged PER-45 CI evidence baseline. The PER-56 branch was created
from that exact remote-main revision. No integration branch or unmerged PER-45
worktree was used. For a same-repository prerequisite, also confirm its merge
commit is an ancestor of refreshed main before starting the dependent.
If a prerequisite is still unmerged, wait and leave the dependent unstarted.

This walkthrough leaves PER-41 parent acceptance, PER-57's pilot, and PER-25's
existing work untouched. It creates no Linear issues or automatic Done updates.

## Reproduce the public enrollment check

Use the Python environment of the trusted installed `local-pr-factory`, from
this checkout:

```sh
/path/to/factory/.venv/bin/python scripts/verify_factory_handoff.py
```

The check loads the actual client `factory.toml` and reads the ready PR body in
`factory-ready-pr-example.md`. Scripted read-only GitHub and Linear adapters
supply the remote metadata. A temporary real SQLite ledger exercises public
`run`, `status`, `pause`, and `resume`, including a controller restart.
It asserts idempotent enrollment, sole task ownership, separate task/shared/other
requirements, preserved pause/resume counters, and no worker requests or passing
gate. The temporary ledger is removed on exit.

Observed result on 2026-10-24 with the local installed controller:

```text
Accepted sample handoff; recovered ownership; pause/resume passed; awaiting CI.
```

Client routing also resolved through `factory status` using profile and label
`lidl-engine`, repository `tomaskub/lidl-engine`, team `PER`, and project
`ec740c75-09c4-42f6-b589-953227c1b366`.

This is scripted enrollment evidence, not live authenticated integration,
CI consumption, formal review, repair, or pilot evidence. It does not promote
client settings into installed policy. The baseline still tests only evidence
production, as declared in `ci/README.md`. Keep required gates disabled until
the separate pilot proves the complete lifecycle. The sample check deliberately
runs outside baseline CI so the application repository does not vendor or install
a controller under review as a trusted dependency.
