"""Verify the documented client handoff against an installed factory controller.

Run with the controller's Python environment, not the CI producer environment.
No network access, publications, or tracker mutations occur.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from local_pr_factory.config import load_profiles
from local_pr_factory.controller import Controller
from local_pr_factory.models import (
    Issue,
    PullRequest,
    Requirement,
    Source,
    SpecReference,
)

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "ec740c75-09c4-42f6-b589-953227c1b366"
REFERENCE = SpecReference("linear:issue", "PER-41")


class ScriptedGitHub:
    def get_pull_request(self, repository: str, number: int) -> PullRequest:
        assert repository == "tomaskub/lidl-engine"
        assert number == 56
        return PullRequest(
            repository=repository,
            number=number,
            author="tomaskub",
            head_repository=repository,
            base_branch="main",
            head_sha="a" * 40,
            base_sha="b" * 40,
            head_branch="feature/per-56-adopt-factory-task-pr-handoff",
            body=(ROOT / "docs/factory-ready-pr-example.md").read_text(),
            labels=("factory",),
        )


class ScriptedLinear:
    def get_issue(self, identifier: str) -> Issue:
        assert identifier == "PER-56"
        return Issue(
            id="1832081b-aae7-4ccc-a3ac-c4fd9691bb9e",
            identifier=identifier,
            team="PER",
            project=PROJECT,
            repository_labels=("lidl-engine",),
            role="implementation",
            specification=REFERENCE,
            parent_id="PER-41",
            title="Adopt task PR handoff and client configuration in Lidl-engine",
            body="Scripted PER-56 task scope for public enrollment verification.",
            requirements=(Requirement("handoff", "Prepare a ready task PR"),),
        )

    def get_specification(self, reference: SpecReference) -> Source:
        assert reference == REFERENCE
        return Source(
            reference=reference,
            team="PER",
            project=PROJECT,
            title="Factory v1 specification",
            body="Scripted shared and later-ticket context.",
            requirements=(
                Requirement("merge", "Maintainer retains merge authority"),
                Requirement("pilot", "Prove the live pilot lifecycle", ("PER-57",)),
            ),
        )


class RecordingWorker:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def execute(self, request: object) -> None:
        self.requests.append(request)


def main() -> None:
    profiles = load_profiles(ROOT / "factory.toml")
    worker = RecordingWorker()
    with TemporaryDirectory(prefix="lidl-handoff-") as directory:
        ledger = Path(directory) / "factory.sqlite"
        with Controller(
            ledger,
            profiles,
            ScriptedGitHub(),
            ScriptedLinear(),
            worker,
            worker_configuration={"engine": "codex", "profile": "review"},
        ) as controller:
            run = controller.run(profile="lidl-engine", pr=56)
            assert run["state"] == "waiting_for_ci"
            assert run["owned_issues"] == ["1832081b-aae7-4ccc-a3ac-c4fd9691bb9e"]
            assert run["repository"] == "tomaskub/lidl-engine"
            assert run["merge_ready"] is False
            requirements = run["requirements"]
            assert [r["key"] for r in requirements["task_criteria"]] == ["handoff"]
            assert [r["key"] for r in requirements["parent_constraints"]] == ["merge"]
            assert [r["key"] for r in requirements["other_ticket_context"]] == ["pilot"]
            assert controller.run(profile="lidl-engine", pr=56) == run
            paused = controller.pause(run["id"], reason="Inspect handoff")
            assert paused["state"] == "paused"
        with Controller(
            ledger,
            profiles,
            ScriptedGitHub(),
            ScriptedLinear(),
            worker,
            worker_configuration={"engine": "codex", "profile": "review"},
        ) as controller:
            assert controller.status(run["id"]) == paused
            resumed = controller.resume(run["id"])
            assert resumed["state"] == "waiting_for_ci"
            assert resumed["owned_issues"] == run["owned_issues"]
            assert resumed["counters"]["pauses"] == 1
            assert resumed["counters"]["resumes"] == 1
            assert resumed["merge_ready"] is False
            assert worker.requests == []
    print(
        "Accepted sample handoff; recovered ownership; pause/resume passed; awaiting CI."
    )


if __name__ == "__main__":
    main()
