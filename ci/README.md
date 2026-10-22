# CI evidence baseline

This is the PER-45 evidence producer for `tomaskub/lidl-engine`. The baseline
tests its own evidence contract. PER-25's application remains on a separate PR.
No offer collection, extraction, validity/filtering, database/migration, desktop
browser, backup/recovery, or launch-quality tests run on this baseline.
No browser screenshots are produced by these contract tests.

## Local checks

Use Python 3.12 or later in a virtual environment.

```sh
python -m pip install -r ci/requirements.txt
python -m pytest --junitxml=evidence/junit.xml
python -m mypy
python -m ruff check ci
python -m ruff format --check ci
```

The complete baseline suite is `ci/tests`. The explicit pytest test path keeps
unmerged application files out of the baseline. When application CI lands,
extend the workflow and scope declaration and preserve its required checks.

## Artifact contract, version 1

The `CI evidence` workflow runs on PRs to `main`, pushes to `main`, and manual
dispatch. It checks out the default event revision. For PRs this normally tests
a synthetic merge, not the PR head. The collector records `git HEAD` and its
parents separately from the event SHA and PR head/base SHA.

The `verify` job runs tests, typechecking, lint, and formatting as separate steps.
The latter three run after test failure if dependency installation succeeded.
Each command tees its output into a diagnostic log and preserves its exit code.
The collection and upload steps run after failure. The `publish` job runs after
`verify`, binds its actual result from `needs.verify.result`, and uploads the
final artifact even when verification failed.

Select workflow `.github/workflows/ci-evidence.yml`, job `verify`, and artifact
`ci-evidence-<run_id>-<run_attempt>`. Artifacts retain these files for 30 days:

- `evidence.json`, metadata and individual check/test execution details.
- `junit.xml`, the original pytest report when pytest produced one.
- `diagnostics/`, available setup and check logs, including failure output.
- `screenshots/`, relevant browser diagnostics if future tests put them there.

`ci-raw-<run_id>-<run_attempt>` is an intermediate diagnostic artifact. Its job
outcome is null and it cannot support review. The final artifact's `job.outcome`
is the completed `verify` job result, not the publisher's status. Consumers must
also verify the publisher/upload succeeded using the GitHub workflow/job APIs.
Artifacts contain relative file references. `workflow.attempt_url` links to the
specific attempt's jobs and logs, and `workflow.run_url` opens downloadable
artifacts. Consumers resolve individual job URLs using job ID `verify` and the
matching run attempt's jobs API.

Top-level identity fields include `schema_version`, `repository`, `context`,
`event_name`, PR `number`/`head_sha`/`base_sha`, `revision.tested_sha` and `parents`,
and workflow `name`/`ref`/`sha`/`run_id`/`run_attempt`. Push and manual runs have
no PR record, and their contexts are `push` and `workflow_dispatch` respectively.
They are diagnostics, not PR-validation evidence.

Each required check records its raw step `outcome`, `step_conclusion`,
`execution`, and available diagnostic path. Tests also record the JUnit path,
individual `classname`, `name`, `duration_seconds`, `outcome`, and failure/skip
messages and details. Outcomes distinguish `passed`, `failed`, `error`, and
`skipped`. A skipped testcase is not evidence that its assertion ran.

If setup prevented the test step from running, its execution is `unexecuted`,
its cases are empty, and its report is null. The producer never creates JUnit.
If the test command ran but the report is absent, malformed, inconsistent, or
empty, execution is `incomplete` with a `report_problem`. The raw file is still
uploaded if present. Cancelled test execution is also incomplete.

The producer reports execution, not merge eligibility. The consumer must match
repository, workflow selector, PR head/base, actual tested commit and merge
parents, run/attempt, artifact expiration, publisher success, verification job
outcome, and all required checks. Missing, cancelled, skipped, unexecuted,
incomplete, unsuccessful, or stale required verification cannot establish a
passing gate. A passing baseline proves nothing about absent application tests
or PER-25 launch acceptance.

If checkout fails, the repository's collector is unavailable. If the runner is
terminated before upload, artifacts may be absent. Missing evidence must block
review; no fallback passing report is generated.

## Live verification

PER-45's live run links and downloaded-artifact observations are recorded in
`docs/ci-evidence-verification.md`. Local contract tests cannot establish that
GitHub Actions executed the workflow or uploaded artifacts.

GitHub behavior used by this contract is documented in the official
[contexts reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts),
[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
and [artifact action documentation](https://github.com/actions/upload-artifact).
