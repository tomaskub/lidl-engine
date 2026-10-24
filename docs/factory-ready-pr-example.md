Adopt task PR handoff and client settings in Lidl-engine.

Factory-Issue: PER-56
Factory-Profile: lidl-engine
Factory-Spec: linear:issue:PER-41

Scope: client settings, implementation/review/planning guidance, and scripted
public enrollment verification. This example claims only PER-56.

Validation: run `scripts/verify_factory_handoff.py` using the installed controller
and the baseline checks in `ci/README.md`. Record actual results in the PR.

Launch obligations: PER-57 proves the live pilot lifecycle. PER-25 application
acceptance and launch checks remain separate. This handoff cannot establish a
passing review, live authentication, or readiness to enable required gates.
