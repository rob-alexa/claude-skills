---
name: pull-request-checklist
description: "GitHub pull request habits from cutting the branch to cleaning up after the merge, with the checks that catch what git and GitHub report as fine. TRIGGER when: creating a branch or worktree; opening, pushing to, syncing, or merging a pull request; resolving a merge conflict; stating a pull request's status; merging a pull request another one is stacked on; or cleaning up after a merge."
metadata:
  version: "1.0"
  license: MIT
---

# pull-request-checklist

What to do with a pull request, in the order you meet it, and the git and GitHub behaviors that make
the obvious move the wrong one: a clean merge that duplicates or loses lines, a status that reads
`UNKNOWN` in a bulk list, a green check that predates the head commit, and a stacked pull request
that closes when the branch under it is deleted. Where your repository's own instructions name its
merge gates, branch prefixes, and reviewers, they win; this skill holds the habits underneath them.

Point-in-time: measured on GitHub repositories, with git on Windows, during 2026. Verify against
your own repository before asserting any of it as current fact.

Placeholders in the commands:

- `<n>`: the pull request number.
- `<base>`: the branch it merges into, which for ordinary work is the integration branch.
- `<integration-branch>`: the branch all work merges into, and the one the main checkout stays on.
- `<root>`: the main checkout. `<wt>`: the task's worktree.
- `<merged>` and `<stacked>`: the numbers of a merged pull request and of one stacked on it.
- `<KEY>-123`: a work-item key, such as a Jira key.

---

## 1. One branch per piece of work

- **At least one branch per work item, and never one spanning several.** Jira's GitHub integration
  links a branch to its work item by the key in the branch name, and a merge check that reads the
  key does the same, so a branch spanning items, or named for a parent item that groups several,
  ties its change to the wrong item or to none, and a check keyed to it can never pass.
- **That includes a branch made by merging two items' branches together** to get past a conflict or
  a failed deploy. It carries no single key, and it re-sends both changes wherever it deploys. When
  one item really needs another, record the dependency and land the earlier one first, or stack the
  later branch on it (see **Stacked pull requests**).
- **Unrelated work gets its own branch and its own pull request.** A doc fix or a piece of
  maintenance you notice along the way goes on its own branch, cut from the integration branch, and
  is never bundled onto a work item's pull request.
- **Decide the branch name before the first push.** A Claude Code harness can designate a branch
  such as `claude/<slug>`; rename it to what the change is, with the repository's prefixes, before
  you push. A check that does not recognize the prefix can treat it fail-safe, and one that reads a
  key from the branch name can post no status at all, which stalls the pull request, since a
  required check that never reports blocks the merge. Renaming after the push is worse: in a
  recorded case, renaming a pull request's head branch on GitHub closed the pull request for good.
  It kept the old head name, and `gh pr reopen` failed because that branch no longer existed. The
  commits survive; the number and any review on it do not.
- **Start from the right branch.** A stale `origin/HEAD` can start a branch, or a worktree a harness
  creates, from the wrong branch. `git rev-parse --abbrev-ref origin/HEAD` should print `origin/`
  plus the integration branch; `git remote set-head origin -a` sets it from GitHub.

## 2. A worktree per task

- **Work on a branch in its own git worktree, and leave the main checkout on the integration
  branch.** Concurrent sessions share the main checkout, so a tracked file changed there is visible
  to all of them and attributable to none, and a fresh session opened there loads its instructions
  and skills from whatever branch the checkout was left on. If you use a hook that refuses writes in
  the main checkout, know what it watches: one that sees only the edit tools cannot see a write made
  by a script or inline Python, so its silence is not proof the checkout is clean.
- **Seed the worktree's git-ignored local files.** A worktree cannot see the main checkout's
  git-ignored files, so a command run in a tree made with a bare `git worktree add` silently loses
  the project's local settings. Create worktrees with a script that copies what the repository
  needs. A worktree Claude Code makes itself (the desktop app's worktree option, or a subagent's)
  gets the files the repository's `.worktreeinclude` lists.
- **Drive the worktree with `git -C <wt>` and absolute paths, and run any other command-line tool in
  a subshell, `( cd <wt> && <command> )`.** Never `cd` into it from your own shell: in Claude Code
  the working directory persists between Bash calls, and Windows will not let a folder be removed
  while a session is sitting in it.
- **Before any commit, `--amend`, `branch -m`, or `switch`, confirm the branch** with
  `git -C <wt> rev-parse --abbrev-ref HEAD` as its own command, and read the answer before acting.
  A check in the same command as the action it gates shows its answer only after the action has run.
  Never do branch surgery over work in progress you did not create.

## 3. Ask before each outward action

Opening, reviewing, commenting on, and merging a pull request reach other people or cannot be
undone, so get a specific go-ahead for each one, naming the pull request, from the person directing
the work: approval to open is not approval to merge, and green checks make a pull request mergeable,
not approved. Show the exact text of a body, review, or comment before posting it, and again after
any edit.

## 4. Open it ready for review

- **Open a pull request ready for review, not as a draft, unless your process holds it as a draft or
  the person asks you to hold it.** A Claude session's own harness commonly tells it to open every
  pull request as a draft, so the wrong default arrives from outside the repository and looks like
  policy. A draft costs three ways: a reviewer workflow that skips drafts asks nobody to review it,
  usually nothing takes it out of draft later, and GitHub refuses to merge it.
- **A draft you opened is yours to clear.** A finished change behind a draft stalls without anyone
  noticing, since nobody is asked to review a draft and the session that opened it has usually moved
  on. When the work is done and the person has not asked to mark it ready, say so in a line and ask
  whether to (`gh pr ready <n>`). When it goes ready, drop any "draft until" line from the body.
- **On a single-commit branch, the squash merge takes its subject from that commit, not from the
  pull request title**, under GitHub's default squash setting
  (`gh api 'repos/{owner}/{repo}' --jq .squash_merge_commit_title` reads `COMMIT_OR_PR_TITLE`). Put
  the title your format calls for in the commit message as well, amending before the first push, or
  pass `gh pr merge <n> --squash --subject "<title>"` when merging.

## 5. Pushing to an open pull request

- **Know whether a push dismisses approvals, and whether a branch must be up to date to merge.**
  Where the base branch's rules dismiss stale reviews on push, every push to an approved pull
  request costs a re-approval, so a push that would dismiss a live approval needs the person to know
  first. Where they do not require a branch to be up to date, a sync is voluntary. Read the rules
  that apply to the base:

  ```bash
  gh api 'repos/{owner}/{repo}/rules/branches/<base>' --jq '.[] | select(.type=="pull_request" or .type=="required_status_checks") | {type, dismiss_on_push: .parameters.dismiss_stale_reviews_on_push, must_be_up_to_date: .parameters.strict_required_status_checks_policy}'
  ```

  That endpoint reads rulesets. Classic branch protection lives at
  `repos/{owner}/{repo}/branches/<base>/protection`, so check there before reading an empty answer
  as "no rule".
- **Don't sync an in-review branch as a reflex.** Merging `<base>` into it to keep it current buys a
  dismissed approval, a merge commit, and a fresh round of checks. A dependency your change needs
  has to be in the environment it runs in, not in your branch's history, so resolve one by merge
  order plus a deploy. Rebasing is no way around this, since a force-push is still a push. Branch
  from the integration branch, do the work, open the pull request, and leave the branch alone.
- **Check the pull request's state before you push, not only before you describe it,** with the
  check as its own command and the push in the next one. In one command the check's answer appears
  only after the push has dismissed the approval, which is how a re-approval given minutes earlier
  was lost in a recorded case. If a live approval would be lost and the push is avoidable, say so
  and let the person decide before you push.
- **Before pushing to clear a red check, ask whether the pull request's own change caused it and
  whether the check is required.** When neither holds, merging as it stands costs less than a push
  that dismisses approvals. Neither a fix merged to the base nor a re-run is sure to clear it.
  GitHub documents that a re-run uses the same commit SHA and ref as the original event, and in a
  recorded case a workflow fix merged to the base left an open pull request red while
  `gh run rerun --failed` reproduced the identical failure. Two cases where a push is the wrong
  move:
  - To re-run a pull request's workflows against the current base, close and reopen it. A
    `pull_request` workflow with the default activity types starts on `reopened`, and approvals
    survive, though a pull request with a merge conflict runs none until a push resolves it. Closing
    a pull request is visible to everyone on it, so offer it before doing it.
  - A job that ends in two to four seconds with no steps and no runner is a GitHub Actions billing
    halt, named in the check run's annotations. Re-running does not help, and a push while it lasts
    spends a live approval on checks that cannot report.
- **After pushing a fix for review feedback, check the reviewer is still requested.** GitHub takes a
  reviewer off the Reviewers field the moment they submit any review, comment-only included. A
  workflow that re-requests reviewers after a dismissed approval or a changes-requested review is
  not triggered by a plain comment, so the fix never reaches the reviewer's list of requested
  reviews. Read `gh pr view <n> --json reviewRequests,latestReviews`; when `reviewRequests` is
  empty, `gh pr edit <n> --add-reviewer <login>` re-requests, with the login from `latestReviews`.
  Re-requesting notifies the reviewer, so treat it like a comment unless your process says
  otherwise.

## 6. Sync only on a real conflict, and check the result

- **Sync only when GitHub reports a real conflict**, or when a branch stacked on another has to take
  that branch's change from `<base>` once it merges (see **Stacked pull requests**). That is the
  merge you cannot avoid, so it is the one to check.
- **A clean merge is not a correct one, and it fails in both directions with nothing reported as an
  error.**
  - **Duplication.** When the branch already carries the base's change in a slightly different form,
    git sees two different additions in neighboring places and keeps both: no conflict, a clean
    tree, and a file that does one thing twice. It shows up in files made of keyless sibling
    elements, such as most XML and many configuration lists.
  - **Loss.** A hand-resolved conflict silently drops the incoming side, in ordinary writing as
    easily as in code. In a recorded case, a conflict in a long Markdown instructions file, resolved
    by string-replacing around the markers, left no markers, read correctly end to end, and was
    missing 14 lines the base had added far from the conflict. A file with no conflict markers left
    is not evidence of a correct resolution.
- **Delete conflict marker lines by line number, highest first**, as in
  `sed -i '1941d;1929d;1911d' <path>`. That is auditable and cannot touch anything else, while
  string-replacing around the markers rewrites the region from what you believe it should say. If
  confidence is gone, `git -C <wt> merge --abort` and redo it.
- **Run three checks on every file the merge touched**, the ones git reported as `Auto-merging` as
  well as the ones it reported as `CONFLICT`:
  1. **Count the occurrences of whatever both sides touched.**
     `grep -c '<the line or element>' <path>` should print `1`, not `2`. Grep too for anything the
     branch removed on purpose: its reappearance is the same defect seen from the other side.
  2. **Diff against the branch tip before the merge**, `git -C <wt> diff <old-tip> -- <path>`
     (`HEAD^1` once the merge is committed). It should be identical, or differ only in ways you can
     name out loud.
  3. **Diff against the base**, `git -C <wt> diff --numstat origin/<base> -- <path>`. The added
     lines should be exactly your own change, and the removed lines exactly the ones your branch
     changed or deleted on purpose, which for a change that only adds is **zero**. Only this check
     catches loss; the first two catch duplication.

  None of the three needs a deploy or a test run, and all are faster than reading the merged file.
  A dry-run deploy or the pull request's checks might catch a duplicate, but neither is guaranteed
  to, since a duplicated element is often perfectly valid.
- **Read mergeability off GitHub, never off your own merge.** A merge driver configured on one
  machine (`git check-attr merge -- <path>` names it) can merge a file cleanly there while GitHub
  reports a conflict on the same pull request. A driver that re-sorts or dedupes also produces a
  diff far larger than the change, which lands on the reviewer who has to re-approve after the push;
  rebuild such a file from the base's exact bytes plus your own elements, then run check 3.

## 7. State a pull request's status from a live check

- **Check live before you state it, never from memory or an earlier turn:**

  ```bash
  gh pr view <n> --json mergeable,mergeStateStatus,reviewDecision,isDraft,headRefOid,commits,statusCheckRollup --jq '{mergeable, mergeStateStatus, reviewDecision, isDraft, headRefOid, headCommitted: .commits[-1].committedDate, checks: [.statusCheckRollup[] | {name: (.name // .context), status, conclusion, state, startedAt}]}'
  ```

- **`mergeable` reads `UNKNOWN` until GitHub computes it, so `UNKNOWN` is never "fine".** Ask about
  the pull request on its own, and again a few seconds later: a bulk `gh pr list --json mergeable`
  returned `UNKNOWN` for 24 of 29 open pull requests, while asking about each one surfaced five
  conflicts. Read `mergeStateStatus` beside it, since `MERGEABLE` only means no conflict and can sit
  next to `BLOCKED`.
- **A green check list is not evidence the checks ran on the current code.** A conflicting pull
  request can stop its workflows running at all, so compare the head commit's time with each check's
  `startedAt`: a check that started before the head commit describes code that is no longer there.
  The error runs the reassuring way, toward believing a stale pass.
- **Read commit statuses and check runs both.** A gate posted as a commit status carries `.state`
  and `.context`, and a check run carries `.conclusion` and `.name`, so a filter on `.conclusion`
  alone silently drops every status-based gate and a blocked pull request reads as ready. Use
  `(.name // .context)` for the name and test `.state` as well as `.conclusion` for the result.
- **A merge GitHub would allow is not the same as ready.** When your process requires something
  GitHub does not enforce, such as a tester's sign-off, report the pull request against that
  ("awaiting testing"), never as "mergeable", "ready", or "nothing blocking it". When to merge stays
  the person's decision.
- **Before asserting a consequence of a rule, confirm its precondition held.** "The push dismissed
  the approval" needs an approval to have existed, so tell *never reviewed* from *approval
  dismissed* in the review list before you say either.
- **A reviewer's list of requested reviews understates what needs them.** A comment-only review
  takes the reviewer off the Reviewers field (see **Pushing to an open pull request**), so the pull
  request drops out of their `review-requested:@me` search while it looks to everyone else like it
  is waiting on them. Cross-check with
  `gh pr list --state open --json number,author,reviewRequests,latestReviews`.
- **`gh pr list --search "<KEY>-123"` matches pull request bodies too**, so it returns any pull
  request that mentions the key. In a recorded case three such searches returned pull requests for
  other work items and together produced a confident wrong claim that three items had shipped. Find
  a work item's pull requests by head branch:

  ```bash
  gh pr list --state all --limit 400 --json number,state,mergedAt,headRefName,title | jq --arg k '<KEY>-123' '.[] | select(.headRefName | test($k; "i"))'
  git branch -r --list '*<KEY>-123*'
  ```

## 8. Stacked pull requests

- **Retarget every pull request stacked on a branch before you merge that branch.** GitHub's
  documentation says that when a merged pull request's head branch is deleted, open pull requests
  based on it are retargeted to the merged pull request's base. Don't count on it. In a recorded
  case, in a repository that deletes head branches on merge, merging a pull request closed the one
  stacked on it two seconds later, its events reading `base_ref_deleted` then `closed`, and the
  merge's own output did not mention it. It was found the next day, one testing step from done, with
  no open pull request left to carry its change. Why the documented retarget did not happen was not
  established.

  Check before every merge, not only one that passes `--delete-branch`, since automatic deletion
  needs no flag:

  ```bash
  gh pr view <n> --json headRefName,baseRefName --jq '"\(.headRefName) -> \(.baseRefName)"'
  gh pr list --base <head-branch-of-n> --state open --json number,title   # must print []
  gh pr edit <stacked> --base <base-of-n>                                 # for each one listed
  ```

  This makes a good pre-merge hook: it costs two `gh` calls, and it needs no override, because
  retargeting is always possible. Name the pull request by number when you merge. With no number,
  `gh pr merge` acts on the pull request for the branch checked out in the current directory, which
  with several worktrees open can be the wrong one.
- **Reopening one that already closed means restoring its base first**, because GitHub will not
  reopen a pull request whose base branch is gone. `gh pr view <merged> --json headRefOid` gives the
  commit to restore:

  ```bash
  git push origin <merged-pr-head-sha>:refs/heads/<deleted-base-branch>   # restore the base
  gh pr reopen <stacked>
  gh pr edit <stacked> --base <base>
  gh pr list --base <deleted-base-branch> --state open                    # must print nothing
  git push origin --delete <deleted-base-branch>
  ```

- **After a squash merge, syncing the stacked branch reports conflicts that are not real.** The
  stacked branch still carries the merged branch's original commits, and git's newest common
  ancestor predates the squash, so files both sides added read as add/add conflicts, and anything
  the merged branch took from `<base>` can conflict with the base's newer copy. In the recorded case
  the sync reported 12 conflicts and none was real. Merge against the real fork point instead, the
  merged branch's commit the stacked branch was built on. It needs git 2.40 or later and a clean
  worktree, and runs as one shell invocation (one Bash call in Claude Code) so the variables
  survive:

  ```bash
  WT=<wt>; B=origin/<base>; M=<merged-pr-head-sha>
  git -C "$WT" diff --quiet HEAD || { echo "STOP: commit the worktree's changes first"; exit 1; }
  F=$(git -C "$WT" merge-base "$M" HEAD)                 # the real fork point
  T=$(git -C "$WT" merge-tree --write-tree --merge-base="$F" "$B" HEAD) \
    || { echo "STOP: real conflicts remain; resolve them as in section 6"; exit 1; }
  T=${T%%$'\n'*}
  OWN=$(git -C "$WT" diff --numstat "$F" HEAD)           # the branch's own change
  GOT=$(git -C "$WT" diff --numstat "$B" "$T")           # what the result adds to the base
  [ -n "$OWN" ] && [ "$OWN" = "$GOT" ] \
    || { echo "STOP: the result is not the base plus the branch's own change"; exit 1; }
  git -C "$WT" merge --no-commit "$B"                    # stops on the false conflicts
  git -C "$WT" read-tree -u --reset "$T"                 # replaces them with the computed result
  git -C "$WT" commit --no-edit
  ```

  The comparison is what makes it safe: the merged result has to differ from the base by exactly
  the branch's own change, file for file and line count for line count.

## 9. After the merge

Once the merge has its go-ahead, and any stacked pull request is retargeted (see **Stacked pull
requests**), the cleanup is routine:

```bash
gh pr merge <n> --delete-branch                    # plus the merge method the repository uses
git -C <root> fetch origin --prune
git -C <root> merge --ff-only origin/<integration-branch>
git -C <root> worktree remove <wt>
```

- **Leave still-open branches alone.**
- **Where the repository deletes head branches on merge**
  (`gh api 'repos/{owner}/{repo}' --jq .delete_branch_on_merge`), the remote branch is already gone:
  skip `git push origin --delete`, which only errors `remote ref does not exist`, and don't report
  the deletion as something you did.
- **`--delete-branch` cannot delete a local branch checked out in a worktree.** Remove the worktree,
  then `git -C <root> branch -D <branch>`.
- **Judge a worktree removal by `git worktree list`, not its exit code.** On Windows,
  `git worktree remove` deregisters the worktree and deletes everything in it, then can exit
  non-zero with `error: failed to delete '<path>': Permission denied` when Windows will not unlink
  the empty folder. That is done apart from the final `rmdir`. A session whose own working directory
  is the worktree can never remove that folder; it clears when the session ends.
- **Clear empty leftover folders with `rmdir`, never `rm -rf`.** `rmdir` refuses a folder that still
  holds anything, so it cannot destroy a worktree with work in it. Establish what is a worktree from
  `git worktree list` first: `git -C <folder>` on a folder that is not a worktree silently answers
  about the enclosing repository, so several folders reporting one identical HEAD are leftovers, not
  checkouts.
- **Leave a `locked` worktree admin folder alone.** An entry under `.git/worktrees/<name>/` with a
  `locked` file reading `initializing` and no `git worktree list` row looks like an interrupted
  `git worktree add`, and it is also exactly what a worktree another session is creating right now
  looks like. `git worktree prune` skips it on purpose, so prune reporting nothing is the signal to
  leave it.
