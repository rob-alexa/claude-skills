# Salesforce and working-method skills for Claude Code

Five [Agent Skills](https://code.claude.com/docs/en/skills) extracted from a working Salesforce
delivery repo and de-identified for public use. Two are Salesforce platform knowledge; three are
working methods that are not platform-specific.

Every one of them exists because something went wrong first. The failures they cover share a shape:
the deploy is green, the tests pass, and the defect is somewhere else entirely.

## The skills

| Skill | What it prevents |
|---|---|
| [`salesforce-user-automation`](skills/salesforce-user-automation/SKILL.md) | Mixed DML on the `User` object. An automation that works on insert and breaks user activation on update; a reconcile job that reports `Completed, NumberOfErrors=0` while doing nothing; a `User` field that deploys but reads as nonexistent; a Chatter membership query that confirms a removal that never happened |
| [`salesforce-files-queries`](skills/salesforce-files-queries/SKILL.md) | An unfiltered `ContentVersion` sweep that under-returns, whose `COUNT` agrees with the wrong number because both travel the same access path |
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
matches what you are doing, so install the ones you will use rather than all five out of habit.

## What was changed on the way out

These came from a private repo for one Salesforce org running a managed package. Removing that context
meant taking out employee and vendor names, org aliases and record counts, internal ticket keys and
repository paths, and links to project instructions that do not exist outside that repo.

What stayed is the mechanism and the evidence for it. Where a claim rests on a single measurement it
says so, and where a cause was never established it says that too rather than offering a tidy
explanation. Two things follow from that. Anything stated as measured was measured on real orgs during
2026, on one estate, so verify it against yours before relying on it. And `design-grilling` carries a
standing frontier of decisions tuned to that estate, which you should expect to replace with your own.

## Attribution and license

MIT. Three of the five are adaptations of Matt Pocock's MIT-licensed skills; see
[NOTICE.md](NOTICE.md) for what came from where and what changed.
