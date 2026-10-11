# Issue tracker: Linear

Issues and specs for this repo live in Linear team `PER` (Personal-automation), under project `Lidl-engine`. Use the connected Linear MCP tools for issue operations.

## Conventions

- Create and update issues with `linear_save_issue`; set `team` to `PER` and `project` to `Lidl-engine` when creating.
- Read an issue with `linear_get_issue` and its comments with `linear_list_comments`. List and search with `linear_list_issues`, scoped to team `PER` and project `Lidl-engine`.
- Add comments with `linear_save_comment`.
- Apply or remove labels with `linear_save_issue`. Resolve triage roles through `triage-labels.md`.
- Close an issue by setting its state to the team's completed state. Add an explanatory comment first when needed.
- Use Linear issue identifiers in references and links.

## When a skill says "publish to the issue tracker"

Create an issue in team `PER`, under project `Lidl-engine`. For implementation tickets under a spec or map, set `parentId` to the parent issue.

## When a skill says "fetch the relevant ticket"

Read the referenced Linear issue and its comments. The user may provide an issue identifier or URL.

## Wayfinding operations

Used by `/wayfinder`. Create the map as a parent issue and its tickets as child issues in project `Lidl-engine`. Use issue relationships for blockers. List children with `linear_list_issues` using `parentId`, scoped to team `PER` and project `Lidl-engine`; choose the first open, unblocked, unassigned child in map order. Claim it by assigning it to `me`. Resolve it with an answer comment, set its state to completed, and add a short decision and issue link to the map.
