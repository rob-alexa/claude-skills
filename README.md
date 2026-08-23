# Claude Code skills from real delivery work

Ten [Agent Skills](https://code.claude.com/docs/en/skills) extracted from a working Salesforce delivery
repo and de-identified for public use. Six are Salesforce platform knowledge, one is Jira Cloud, and
three are working methods that are not platform-specific.

## Salesforce

| Skill | What it prevents |
|---|---|
| [`salesforce-flow-and-ui-defects`](skills/salesforce-flow-and-ui-defects/SKILL.md) | Defects that deploy clean and fail only on screen: `$User.Id` being 15 characters against an 18-character lookup so a decision never matches, a blank cross-object merge field, a picklist default that applies to no existing record, an LWC invisible on phones, a related-list tab that renders empty, an orchestration that needs a Username where you gave it an Id, and a validation rule that rolls back the record it was protecting |
| [`salesforce-data-loading`](skills/salesforce-data-loading/SKILL.md) | A migration that lands stamped with the loading user and the load date, which no later update can correct, a blanking load that reports success without clearing anything, a unique field discovered 8,604 failures in, and a row count that is wrong because long text contains newlines |
| [`salesforce-user-automation`](skills/salesforce-user-automation/SKILL.md) | Mixed DML on the `User` object: an automation that works on insert and breaks user activation on update, a reconcile job reporting `Completed, NumberOfErrors=0` while doing nothing, a `User` field that deploys but reads as nonexistent, and a membership query that confirms a removal that never happened |
| [`salesforce-business-days`](skills/salesforce-business-days/SKILL.md) | A "Default" Business Hours set that is quietly 24/7, a holiday list a deploy silently replaces, a set rename that creates a second set you cannot delete, and reaching for Apex when `TODAY() + 7` is exact |
| [`salesforce-code-analyzer-gate`](skills/salesforce-code-analyzer-gate/SKILL.md) | A red Code Analyzer check caused by your branch's config vintage rather than your code, `ApexCRUDViolation` on every new class, whole-file findings you did not write, and the Windows locale bug that surfaces as a Critical engine error |
| [`salesforce-files-queries`](skills/salesforce-files-queries/SKILL.md) | An unfiltered `ContentVersion` sweep that under-returns, whose `COUNT` agrees with the wrong number because both travel the same access path |

## Jira

| Skill | What it prevents |
|---|---|
| [`jira-rest-writes`](skills/jira-rest-writes/SKILL.md) | Writes that return `201`/`204` and store the wrong thing: prose flattened into a single ADF node, an assignment resolved to a non-assignable service-desk account, a duplicate link recorded backwards, a resolution silently left as `Done`, and `/editmeta` reporting a field unwritable when the write succeeds. Includes [`jira-text-to-adf.py`](skills/jira-rest-writes/jira-text-to-adf.py) |

## Working methods

| Skill | What it prevents |
|---|---|
| [`design-grilling`](skills/design-grilling/SKILL.md) | A build that is internally coherent, carefully specified, and answering a question nobody ever confirmed. Works the open decisions as a tree, in rounds, recommending an answer to each |
| [`session-handoff`](skills/session-handoff/SKILL.md) | A fresh session re-solving what the last one settled, and the compounding token cost of never starting a fresh one |
| [`stakeholder-questionnaire`](skills/stakeholder-questionnaire/SKILL.md) | A questionnaire that asks its own author's questions back at them, or that asks a business reader something only answerable in git |

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
matches what you are doing, so install the ones you will use rather than all ten out of habit.

## What was changed on the way out

These came from a private repo for one Salesforce org running a managed package. Removing that context
meant taking out employee and vendor names, org aliases and record counts, internal ticket keys and
repository paths, and links to project instructions that do not exist outside that repo.

What stayed is the mechanism and the evidence for it. Where a claim rests on a single measurement it
says so, and where a cause was never established it says that too rather than offering a tidy
explanation. Two things follow. Anything stated as measured was measured on real orgs during 2026, on
one estate, so verify it against yours before relying on it. And `design-grilling` carries a standing
frontier of decisions tuned to that estate, which the skill tells you to replace with your own.

## Attribution and license

MIT. Three of the ten are adaptations of Matt Pocock's MIT-licensed skills; see [NOTICE.md](NOTICE.md)
for what came from where and what changed.
