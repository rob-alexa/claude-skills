# Claude Code skills from real delivery work

A collection of 11 [skills](https://code.claude.com/docs/en/skills) extracted from a working
Salesforce delivery repo and de-identified for public use: 7 on Salesforce platform knowledge, 1 on
Jira Cloud, and 3 working methods that are not platform-specific.

## Salesforce

| Skill | What it does |
|---|---|
| [`salesforce-flow-and-ui-defects`](skills/salesforce-flow-and-ui-defects/SKILL.md) | Catalogs the Flow and Lightning failures that pass a clean deploy and surface only on screen, with the cause and the fix for each: the 15-against-18-character `$User.Id` comparison, a blank cross-object merge field, a picklist default that reaches no existing record, an LWC missing from phones, a layout-fed related-list tab, an orchestration Resource that wants a Username, and a validation rule that rolls back the record it guards. Also covers how to exercise a screen flow whose Submit is destructive |
| [`salesforce-flow-versions`](skills/salesforce-flow-versions/SKILL.md) | Establishes which version of a flow an org is actually running, since source status, a deploy result, a retrieve, and `FlowDefinitionView` each report on a different one. Covers activation and deactivation, the three routes to an `InvalidDraft` that deployed green, deleting a flow safely, why a dependency query returning nothing does not mean a field is safe to delete, and why a running orchestration keeps the stages it started on |
| [`salesforce-data-loading`](skills/salesforce-data-loading/SKILL.md) | Walks the design of a bulk load: which describe flags decide the approach before you build the file, the two permissions that let a load set audit fields and inactive owners, how to derive an undecided value from records that already carry it, and the four operations that report success while doing something other than what you meant |
| [`salesforce-user-automation`](skills/salesforce-user-automation/SKILL.md) | Explains why automation touching `User` alongside any non-setup object breaks, and how to structure it so it does not: the async path, the chained Queueable, and tests that actually exercise the collision. Also covers `User` fields that describe as nonexistent, and querying Chatter membership without silently dropping inactive members |
| [`salesforce-business-days`](skills/salesforce-business-days/SKILL.md) | Sets up Business Hours properly: how to measure what a set really is, since the metadata cannot tell you, a two-set design that lets holiday-aware and holiday-blind automation coexist, the deploy semantics for holidays, and when business-day math needs Apex rather than a plain `TODAY() + 7` |
| [`salesforce-code-analyzer-gate`](skills/salesforce-code-analyzer-gate/SKILL.md) | Diagnoses a red Code Analyzer check: which rules can fail the job rather than report, what `ApexCRUDViolation` is asking for, when a finding comes from your branch's config vintage rather than your code, and how to force a check to re-run without dismissing an approval. Includes the Windows locale fix for the flow engine |
| [`salesforce-files-queries`](skills/salesforce-files-queries/SKILL.md) | Builds a file population from `ContentDocumentLink` rather than a `ContentVersion` sweep, explains why the obvious sanity check confirms the wrong number, and says where to chunk a long `IN` list |

## Jira

| Skill | What it does |
|---|---|
| [`jira-rest-writes`](skills/jira-rest-writes/SKILL.md) | REST recipes for every Jira Cloud write, each paired with the read-back that confirms it: create, edit, comment, transition, assign, link, sprint, and Story Points. Covers building ADF documents, resolving an assignable account on a site that also runs Service Management, and which fields have to go in a call of their own. Includes [`jira-text-to-adf.py`](skills/jira-rest-writes/jira-text-to-adf.py) |

## Working methods

| Skill | What it does |
|---|---|
| [`design-grilling`](skills/design-grilling/SKILL.md) | Works the open decisions on a piece of work as a tree, in rounds, putting the whole frontier at once with a recommended answer to each, and separates the facts you should look up yourself from the decisions only a person can make |
| [`session-handoff`](skills/session-handoff/SKILL.md) | A four-section handoff file per task, and the rule for when to read and write one, so a fresh session continues the work rather than re-deriving it |
| [`stakeholder-questionnaire`](skills/stakeholder-questionnaire/SKILL.md) | Turns questions you cannot answer into one document a named colleague fills in, by interviewing whoever is directing the work about the send rather than about the subject |

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
matches what you are doing, so install the ones you will use rather than all 11 out of habit.

## What was changed on the way out

These were written for day-to-day Salesforce delivery work and rewritten for general use, with names,
identifiers, and organization-specific references removed.

What stayed is the mechanism and the evidence for it. Where a claim rests on a single measurement it
says so, and where a cause was never established it says that too rather than offering a tidy
explanation. The measurements come from real environments during 2026, but all from one organization,
so verify anything you plan to rely on against your own. And `design-grilling` closes with a list of Salesforce
decisions drawn from that same source, which the skill tells you to replace with your own.

## Attribution and license

MIT. Three of the 11 are adaptations of Matt Pocock's MIT-licensed skills; see [NOTICE.md](NOTICE.md)
for what came from where and what changed.
