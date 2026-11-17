# Claude Code skills from real delivery work

A collection of 16 [skills](https://code.claude.com/docs/en/skills) extracted from a working
Salesforce delivery repo and de-identified for public use: 10 on Salesforce platform knowledge, 1 on
GitHub pull requests, 2 on Jira, and 3 working methods that are not platform-specific.

## Salesforce

| Skill | What it does |
|---|---|
| [`salesforce-flow-and-ui-defects`](skills/salesforce-flow-and-ui-defects/SKILL.md) | Catalogs the Flow and Lightning failures that pass a clean deploy and surface only on screen, with the cause and the fix for each: the 15-against-18-character `$User.Id` comparison, a blank cross-object merge field (and the one hop that does resolve), a picklist default that reaches no existing record, an LWC or Dynamic Related List missing from phones, a layout-fed related-list tab, an error screen that misreports what a fault path already saved, an orchestration Resource that wants a Username, and a validation rule that rolls back the record it guards. Also covers how to exercise a screen flow whose Submit is destructive. |
| [`salesforce-flow-versions`](skills/salesforce-flow-versions/SKILL.md) | Establishes which version of a flow an org is actually running, since source status, a deploy result, a retrieve, and `FlowDefinitionView` each report on a different one. Covers activation and deactivation, the routes to an `InvalidDraft` that deployed green (including one no deploy can overwrite), diffing production, a sandbox, and source three ways, deleting a flow safely, why a dependency query returning nothing does not mean a field or subflow is safe to delete, and why a running orchestration keeps the stages it started on. |
| [`salesforce-data-loading`](skills/salesforce-data-loading/SKILL.md) | Walks the design of a bulk load: which describe flags and CLI flags decide the approach before you build the file, the two permissions that let a load set audit fields and inactive owners, how to pre-flight a file against what the org already holds, how to check a load against its source without the comparison lying, how to derive an undecided value from records that already carry it, and the automation that reports success while storing something other than what you loaded. |
| [`salesforce-metadata-deploy`](skills/salesforce-metadata-deploy/SKILL.md) | Reads a deploy's verdict in the order that holds up (`status`, then each component, then the org), since a failed deploy still lists its components as successes. Covers the deploys that remove something while reporting success: a permission set or permission set group replaced wholesale with no per-user audit row, and an LWC or Aura bundle losing files it did not carry. Also covers a scheduled job's class blocking a deploy, and a Lightning page placement blocking a field delete that the dependency query never shows. |
| [`salesforce-picklist-changes`](skills/salesforce-picklist-changes/SKILL.md) | Decides whether you may change a picklist's values and shows what a deploy does to the ones your file leaves out: replace semantics in both directions, what `restricted` does and does not enforce, what a subscriber may edit on a packaged picklist, the inactive values a retrieve cannot see, comparing value sets across orgs without entity or line-ending errors, decoding `validFor`, and promoting a picklist to a global value set. |
| [`salesforce-user-automation`](skills/salesforce-user-automation/SKILL.md) | Explains why automation touching `User` alongside any non-setup object breaks, and how to structure it so it does not: the async path, the chained Queueable, and tests that actually exercise the collision. Also covers `User` fields that describe as nonexistent, and querying Chatter membership without silently dropping inactive members. |
| [`salesforce-business-days`](skills/salesforce-business-days/SKILL.md) | Sets up Business Hours properly: how to measure what a set really is, since the metadata cannot tell you, a two-set design that lets holiday-aware and holiday-blind automation coexist, the deploy semantics for holidays, when business-day math needs Apex rather than a plain `TODAY() + 7`, and how a formula can skip holidays it cannot read. |
| [`salesforce-code-analyzer-gate`](skills/salesforce-code-analyzer-gate/SKILL.md) | Diagnoses a red Code Analyzer check: which rules can fail the job rather than report, what `ApexCRUDViolation` is asking for, when a finding comes from your branch's config vintage rather than your code, how to suppress a finding and keep tooling scripts out of the LWC rules, why a green scan is not a compile check, and how to force a check to re-run without dismissing an approval. Includes the Windows locale fix for the flow engine. |
| [`salesforce-files-queries`](skills/salesforce-files-queries/SKILL.md) | Builds a file population from `ContentDocumentLink` rather than a `ContentVersion` sweep, explains why the obvious sanity check confirms the wrong number, says where to chunk a long `IN` list, and explains why relinking a file attached in a Chatter post loses it for good. |
| [`salesforce-mobile-emulator-qa`](skills/salesforce-mobile-emulator-qa/SKILL.md) | Shows how a screen really renders on a phone by running the Salesforce mobile app on an Android emulator, since Salesforce picks the form factor from the user agent and no resized browser can show it. Covers which system image and app build actually run, moving the app between orgs and confirming which one it is signed in to, and diagnosing blank pages and a stale cached layout over the WebView's DevTools socket, with a small DevTools client included. |

## Jira

| Skill | What it does |
|---|---|
| [`jira-rest-writes`](skills/jira-rest-writes/SKILL.md) | REST recipes for every Jira Cloud write, each paired with the read-back that confirms it: create, edit, comment, transition, assign, link, close with a resolution, sprint, and Story Points. Covers building ADF documents, resolving an assignable account on a site that also runs Service Management, which fields have to go in a call of their own, and the reads that return a confident wrong answer: the removed search endpoints, a custom field read by the wrong id, and history claimed without the changelog. Ships with a converter that turns plain text into the ADF payload the endpoints expect, so paragraphs, bullets, numbered lists, and `@[Display Name]` mentions survive instead of flattening into a single block. |
| [`qa-handoff`](skills/qa-handoff/SKILL.md) | Writes a QA sub-task a tester can act on without you: numbered one-check-per-step guidance, the field combination that drives the behavior rather than test record Ids that drift, a step for any field taken off a page, the sandbox checks that give a false pass, screenshots placed inline at the step they illustrate, desktop and phone captures, and the order to create and transition sub-tasks in so Jira automation does not close the parent out from under you. |

## GitHub

| Skill | What it does |
|---|---|
| [`pull-request-checklist`](skills/pull-request-checklist/SKILL.md) | Carries a pull request from branch to cleanup with the checks that catch what git and GitHub report as fine: a clean merge that duplicates or loses lines, `mergeable` reading `UNKNOWN` in bulk lists, a green check that predates the head commit, a status-based gate that a check-run filter drops, and a stacked pull request that closes when its base branch is deleted, with the reopen recipe and a fork-point `merge-tree` for syncing after a squash. |

## Working methods

| Skill | What it does |
|---|---|
| [`design-grilling`](skills/design-grilling/SKILL.md) | Works the open decisions on a piece of work as a tree, in rounds, putting the whole frontier at once with a recommended answer to each, and separates the facts you should look up yourself from the decisions only a person can make. |
| [`session-handoff`](skills/session-handoff/SKILL.md) | A four-section handoff file per task, and the rule for when to read and write one, so a fresh session continues the work rather than re-deriving it. Carries the cost case for actually stopping: re-read context is billed every turn, so it compounds with position, and in one team's measured usage a request past turn 200 re-read 619K tokens against 24.8K at turn 1, with 47.7% of all spend sitting past turn 100. |
| [`stakeholder-questionnaire`](skills/stakeholder-questionnaire/SKILL.md) | Turns questions you cannot answer into one document a named colleague fills in, by interviewing whoever is directing the work about the send rather than about the subject. When the recipient has to type into it, covers choosing a fillable PDF or a Word document, and the pypdf trap that writes a fillable PDF holding no fields. |

## Install

Copy the ones you want into your skills directory. Personal, available in every project:

```bash
cp -r skills/salesforce-user-automation ~/.claude/skills/
```

Or per project, checked in with the repo, so the whole team gets them:

```bash
cp -r skills/design-grilling .claude/skills/
```

Claude Code loads each skill's `description` on every request and the body only when the description
matches what you are doing, so install the ones you will use rather than all 16 out of habit.

## What was changed on the way out

These were written for day-to-day Salesforce delivery work and rewritten for general use, with names,
identifiers, and organization-specific references removed.

What stayed is the mechanism and the evidence for it. Where a claim rests on a single measurement it
says so, and where a cause was never established it says that too rather than offering a tidy
explanation. The measurements come from real environments during 2026, but all from one organization,
so verify anything you plan to rely on against your own. And `design-grilling` closes with a list of
Salesforce decisions drawn from that same source, which the skill tells you to replace with your own.

## Attribution and license

MIT. Three of the 16 are adaptations of Matt Pocock's MIT-licensed skills; see [NOTICE.md](NOTICE.md)
for what came from where and what changed.
