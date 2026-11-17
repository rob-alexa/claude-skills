---
name: session-handoff
description: "Carrying a multi-session task across sessions. TRIGGER when: starting work on any work item or named ongoing task, before building any script, derivation, or load for one, resuming something a previous session started, wrapping up with work unfinished, or the conversation has been summarized and the work is still going. Check whether a task folder already exists before building; read the handoff before starting; write one before stopping."
metadata:
  version: "1.1"
  license: MIT
  adapted_from: "https://github.com/mattpocock/skills (handoff) - MIT, Copyright (c) 2026 Matt Pocock"
---

# session-handoff

A **handoff** is one dated Markdown file per task that lets a fresh session continue the work without
rediscovering it. Read one before you start; write one before you stop.

Adapted from Matt Pocock's `handoff` skill (https://github.com/mattpocock/skills, MIT), with the
storage location changed. His saves to the OS temporary directory; here the file has to survive,
because the value shows up days later.

## Two reasons this pays, and the second is the one nobody feels

- **A new session re-solves what the last one settled.** Recorded case: a session rebuilt a
  parent-record derivation from scratch, reached 91.7% accuracy, and called the remainder unsafe to
  automate, while a script in the same task folder already sat at 98.8% with the decision encoded in
  its docstring. It had been solved before, in that folder, by an earlier session.

- **A long session costs many times what a fresh one does.** Re-read context is billed every turn, so
  cost compounds with position. Measured across 309 transcripts of one team's usage in 2026: a request
  at turns 201-400 re-read 619K tokens against 24.8K at turn 1, and **47.7% of all spend sat past turn
  100**. A handoff plus a genuinely new session resets that baseline. Letting the conversation be
  summarized instead keeps you in the same session, so the compounding continues.

## Before you start: look first, then work

**Run this before building anything for an ongoing task, including when you have no reason to think a
folder exists.** A check that opens "when work touches an existing task folder" is conditional on
already knowing the answer, and that is the one state in which nobody runs it.

1. **Check whether the task has a folder at all**, by its tracker key and by subject: list the task
   folders and filter on both. Recorded case: a session drafted a complete QA handoff from scratch
   while the task's folder already held the payloads, a script to post them, and a scheduled job
   addressed to a different tester. Nothing about the work item, the branch, or the PR hinted the
   folder was there, which is the point: when task folders are git-ignored, neither git nor the
   tracker can show you one, so the only way to find it is to look. **Search by the record's name and
   id as well as the key**, since work can predate the work item: in another case the folder that
   explained a deleted row was named after the record, because that work happened before any work
   item existed.
2. **List the folder.** Read the newest `HANDOFF-*.md` in full.
3. **Read the docstring of every script whose name is near your problem.** The handoff is the map; the
   scripts are the answers, and their docstrings carry the decisions and the measured accuracy.
4. **Only then start building.** A derivation, classifier, load, or query you are about to write from
   scratch is the exact thing that folder most likely already holds.

If your task folders are git-ignored, search their contents with `grep -rl` in a shell, not Claude
Code's Grep tool, which honors `.gitignore` and answers "No files found" there.

**Then widen the search to the repo, because it has to be wider than it feels.** Recorded case: a
session looked for an existing tool by listing `scripts/` for names it might have and running one
`grep -r` under `scripts/`, found nothing, concluded none existed, and wrote its own, which was subtly
wrong. The canonical one was a ready-made snippet in a doc. So search the documentation folder,
`.claude/skills/`, and `.github/` as well as `scripts/`, and search for what the tool would **do**
(an API it would call, a flag it would pass) as well as what it might be called. Scope the search to
those paths, not the repo root, since a repo-wide `grep -r` walks ignored directories and can time
out.

## Before you stop: write one

Write `<task-folder>/HANDOFF-<YYYY-MM-DD>.md`. A new dated file each time, never an edit of
yesterday's, so the sequence stays readable.

Four sections, and the last two are what make it worth reading:

```
# <task> - handoff, <date>

## State
What is true now, each figure carrying its source tag and naming the environment it came from.
The branch, the working tree path, the PR number, and the target environment.

## Open
The decisions still unsettled and who owns each. When nothing is open, say NOTHING outright:
an explicit empty list is information, and a missing section reads as an omission.

## Traps this task has already paid for (do not rediscover)
Each wrong turn already taken, and what it cost. This is the section that saves the next session.

## Next
The first thing to do, specific enough to act on without re-deriving why.
```

**Reference rather than restate.** Anything already carried by the branch, the PR, the tracker item,
the project instructions, or a script in the folder gets a path or a number, not a copy. A handoff
that restates the diff goes stale the moment either changes, and length is what stops it being read.

**Redact.** No credentials, tokens, or personal data.

**Tag every figure with its source, and say which environment it came from.** A number carried
forward with no date turns into a fact nobody can check, which is how a stale count reaches a
stakeholder as current. Each paragraph holding a figure carries one of four tags:

- `[live YYYY-MM-DD]`: read from a live system on that date, and re-readable.
- `[unrecoverable YYYY-MM-DD]`: live on that date and impossible to re-read, such as a point-in-time
  count with no history behind it.
- `[doc]`: taken from a work item, a record, a PR, or something a named person said.
- `[inferred]`: your own reasoning.

`[unrecoverable]` is the one that gets skipped and the one that matters most, since a bare date on a
value nobody can re-check reads as reassurance. A hook can enforce the tags by refusing a handoff
write whose **bold** figure has no tag in its paragraph. `[inferred]` always passes such a check: the
tag says how you know, never that you verified.

## Name a handoff to a PERSON with its task folder, never the bare filename

Say `<task-folder>/HANDOFF-2026-08-20.md`, or link the full path, and never `HANDOFF-2026-08-20.md` on
its own. **In a Markdown link it is the visible text that has to carry the folder, not only the
target**, because a rendered link shows its text and nothing else, so a bare filename as the link
text still makes the reader do the folder lookup. All the identity is in the **folder** and only the
date is in the filename, so every task folder holds a file with the same name and the bare one
identifies nothing. Measured on one repo: 12 handoff files across six task folders, six of them in a
single folder. Reading the bare name back to somebody makes them redo the folder lookup you already
did, and date-suffixed variants (`HANDOFF-2026-08-19-afternoon.md`) are harder still to place.

The convention itself is right and stays as it is, so this is a rule about how a handoff is REFERRED
to and never a reason to rename one. Inside the file the folder is already the context, so it does not
apply there.

## Then actually start a new session

The saving comes from the fresh context, not from the file. Hand off, end the session, and open a new
one pointed at the handoff. Carrying on in the same conversation after writing one pays the full
re-read and gains nothing.

Point the new session at the handoff with a short prompt: the task, the handoff's **absolute** path in
the main checkout, and an instruction to read it in full and then do its **Next** step. A new git
worktree does not carry git-ignored files, so if the task folder is ignored, a relative path or a
bare filename finds nothing there. And start the session fresh, not as a fork of this one: a fork
carries the whole conversation across, which is the cost the handoff exists to shed.

If your harness can surface the per-turn token figure, wire it to say so rather than to block. What
that removes is the part where nobody could see the number; the decision to stop stays the user's.

**Two absolute token thresholds held up, each firing once and escalating:** 300K to offer a handoff,
and 400K to say plainly that continuing is the expensive choice and stop. Make them absolute counts
rather than a percentage of anything, so they mean the same thing for a light user and a heavy one.

**Write the handoff when either line fires, not only at the top one.** At 300K, offer the new session
and carry on only if the user says to; at 400K, stop. A line that only offers a handoff leaves nothing
to hand over if the session carries on and then ends.

To check them against your own usage, the curve they came from averaged 199K at turn 50, 287K at
turn 100, and 435K at turn 200, which puts 300K near turn 110 and 400K near turn 180. Growth ran
about 1.5K per turn, so 100K of headroom is roughly 65 turns.

**Measure your own before adopting these.** They come from one person's sessions, and that person is
the heaviest user of the repo they were measured in. The mean and median tracked closely at every
turn sampled, so they are not distorted by outliers, but they still describe one curve.

Three things measurement settled, and all three were wrong beforehand. **A first threshold at 150K
was too early**: it landed around turn 25, before most sessions have done anything, so the honest
response to it was always "nothing to do yet". **The 200K notice that replaced it was too early as
well**, and a later measurement retired it: by then a session in that setup opened at about 140K
tokens per turn, so 89% of 695 sessions over about seven weeks crossed 200K (one machine's
transcripts), and sessions ended no more often just after the notice than just before it. Endings did
jump at 300K and 400K, which is why those two stay. And **a top threshold at 500K was far too late**,
at somewhere past turn 250, by which point the expensive turns have already been paid for.
