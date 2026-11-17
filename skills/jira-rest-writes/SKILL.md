---
name: jira-rest-writes
description: "Writing to Jira Cloud from the CLI: create, edit, comment, transition, assign, link, close with a resolution, sprint, Story Points. TRIGGER when: composing a Jira description or comment, assigning or @-mentioning, adding to a sprint, setting or reading points or another custom field, searching with JQL, reading an issue's history, or verifying a write landed. Most traps here return success, or a confident null, while storing or reading the wrong thing."
metadata:
  version: "1.1"
  license: MIT
---

# jira-rest-writes

Endpoints, recipes, and verification patterns for writing to Jira Cloud over REST. What makes this
worth a skill is that **most of the failures return `200`, `201`, or `204`** while storing something
other than what you meant, and the read-side traps return a confident `null` or an empty list, so
the whole file is organized around reading the write back and making sure the read asked the right
question.

Point-in-time: verified against Jira Cloud during 2026. Confirm anything volatile against your own
site.

## Setup and auth

Read and write through the REST API with `curl --netrc`, authenticated by a classic Atlassian **API
token** in `~/.netrc` for your site's machine. A box without it fails
`curl: (26) .netrc error: no such file`, which is the one thing to check before diagnosing anything
else:

```bash
test -f ~/.netrc && grep -q your-site.atlassian.net ~/.netrc && echo ok
```

**A SCOPED API token must call `https://api.atlassian.com/ex/jira/<cloudId>`, never
`https://<site>.atlassian.net`.** The site URL simply does not serve scoped tokens, and it returns
*inconsistent* status codes (401 on one endpoint, 404 on another), which reads like a credential
problem and is not. A **classic** unscoped token does work against the site URL, which is why a
person's own classic token succeeds on the identical path where, for example, a CI job's scoped token
fails. This one cost weeks to diagnose. The cloudId is public, so fetching it needs no credential:
`curl -s https://<site>.atlassian.net/_edge/tenant_info | jq -r .cloudId`. Every recipe in this skill
assumes a classic token on the site URL.

**`acli` is not the route.** It stays installed and authenticated, which is the trap, because it looks
like it works. It omits the assignee from its output, silently does nothing when told to assign, strips
`mention` nodes, flattens prose into a single ADF node, and cannot upload an attachment at all. Every
one of those reports success. Everything it does, REST does verifiably.

**Inside a Claude session, the Atlassian MCP connector is a working fallback** and needs no local
file. It returned the assignee correctly where `acli` omitted it, and it carries
`lookupJiraAccountId`, which settles **The `qm:` dual-account trap** directly. It cannot serve a
script or CI, so anything that runs unattended uses `curl --netrc`. Its write scope as last tested in
2026: `editJiraIssue` set the assignee, a custom number field, and a multi-paragraph description,
which lands as real paragraph nodes when passed `contentFormat: "markdown"` with blank lines between
paragraphs. `transitionJiraIssue` moves an issue by an id from `getTransitionsForJiraIssue`, though it
was refused once and worked about three weeks later, so re-test it before relying on it. Its read side
returns a description as Markdown whatever format you request, so count ADF blocks with a `curl` GET
on v3, never through the connector.

**Before planning writes to a project you have not written to, check your own permissions.**
Browsing and commenting imply neither create nor edit: on one Jira Product Discovery project, the
account behind a working token could browse and comment but could not create or edit ideas.

```bash
S=https://your-site.atlassian.net
curl -s --netrc -G "$S/rest/api/3/mypermissions" --data-urlencode 'projectKey=PROJ' \
  --data-urlencode 'permissions=CREATE_ISSUES,EDIT_ISSUES' \
  | jq -r '.permissions[] | "\(.key) \(.havePermission)"'
```

## Endpoint map

Base: `S=https://your-site.atlassian.net`, every call `curl --netrc`. Platform API v3 for issues, the
agile API for boards and sprints.

| Operation | Call | Success |
|---|---|---|
| Create | `POST $S/rest/api/3/issue` | `201`, key in `.key` |
| Edit fields | `PUT $S/rest/api/3/issue/<KEY>` | `204` |
| Comment | `POST $S/rest/api/3/issue/<KEY>/comment` | `201`, comment id in `.id` |
| Transition | `POST $S/rest/api/3/issue/<KEY>/transitions` | `204` |
| Assign | `PUT $S/rest/api/3/issue/<KEY>/assignee` | `204` |
| Link | `POST $S/rest/api/3/issueLink` | `201` |
| Attach a file | `POST $S/rest/api/3/issue/<KEY>/attachments` | `200` |
| Read anything | `GET $S/rest/api/3/issue/<KEY>?fields=…` | `200` |
| Read history | `GET $S/rest/api/3/issue/<KEY>/changelog` | `200`, paged in `.values[]` |
| Read watchers | `GET $S/rest/api/3/issue/<KEY>/watchers` | `200` |
| Search | `GET $S/rest/api/3/search/jql?jql=…` | `200`, paged by `nextPageToken`, no `.total` |

**Every write is confirmed by reading it back, never by the status code.** A `204` means the call was
accepted, and several of the traps below produce a `204` alongside the wrong stored value.

**An Automation for Jira rule can act on your write, so what you read back might not be only what you
sent**: a sub-task that appeared after a sprint add, a status that moved on its own, a link nobody
typed. **And a read-back fired a second or two after a transition can return the PRE-automation
state.** The `GET` is truthful and already stale, which is how a transition that a rule reverted two
seconds later was first reported as a success. Wait about 20 seconds anywhere a rule might fire, and
where you need to know what actually happened rather than what is true now, read the **changelog**
rather than the current status: the `author` on each entry shows who or what made that change (recipe
in **History, search, and custom fields**).

### Allowlisting writes in Claude Code: spell the command the way the rule does

**A Bash permission rule matches the start of the command**, so a rule such as
`Bash(curl --netrc -X POST https://your-site.atlassian.net*)` (with a matching `-X PUT` rule) matches
only a write that begins with exactly that text. A flag ahead of `-X`, the short `-n`, a variable
such as `"$S/…"`, or an opening quote where the host belongs each fall through to whatever your
permission mode does with an unmatched command: a prompt, or in auto mode the classifier, which has
blocked that spelling of a Jira write. Put `-s`, `-w`, `-H`, `-o`, and `--data` after the URL, as
every write recipe in this skill does. The reads use `$S` for brevity, so spell them out the same way
if you allowlist reads too.

**A block is evidence about the command's spelling, not about a policy.** Fix the spelling, and never
re-run the identical command: that reads as a bypass attempt, and in one recorded session it closed
the route for the rest of the session, read-only GETs to the same host included. Don't record a block
as "Jira writes are refused" in a note or memory either, since that teaches the next session to stop
trying.

## Common operations

```bash
S=https://your-site.atlassian.net

# Issue types on a project, with the exact sub-task type name:
curl -s --netrc "$S/rest/api/3/project/PROJ?expand=issueTypes" \
  | jq -r '.issueTypes[] | "\(.name) subtask=\(.subtask)"'

# Create. Build the description as ADF first (see "Build a description as an ADF document"): the
# converter emits the {"fields": …} envelope this endpoint wants, so add project, issuetype, and
# summary into that same .fields object.
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue -s \
  -H "Content-Type: application/json" --data @payload.json | jq -r '.key'
# Sub-task: add  "parent":{"key":"PROJ-177"}  and  "issuetype":{"name":"Sub-task"}  to .fields

# Transition. Read the ids live every time: names are not accepted, and the ids are per workflow.
curl -s --netrc "$S/rest/api/3/issue/PROJ-177/transitions" \
  | jq -r '.transitions[] | "\(.id) \(.to.name)"'
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-177/transitions -s \
  -H "Content-Type: application/json" --data '{"transition":{"id":"31"}}'

# Comment (ADF body; see "Build a description as an ADF document")
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-177/comment -s \
  -H "Content-Type: application/json" --data @payload.json

# Attach a file. The X-Atlassian-Token header is REQUIRED; without it the call is refused as XSRF.
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-177/attachments -s \
  -H "X-Atlassian-Token: no-check" -F "file=@screenshot.png"
```

**Deleting an issue cannot be undone, and deleting a parent takes its sub-tasks with it.** Save the
JSON of the issue and of each sub-task (`GET $S/rest/api/3/issue/<KEY>`) before you delete. Over
REST, `DELETE /rest/api/3/issue/<KEY>` refuses an issue that has sub-tasks unless you pass
`deleteSubtasks=true` (per Atlassian's REST reference), and reaching for that flag is the moment to
stop and check.

---

## History, search, and custom fields

**A current field value says nothing about when or why it got that way, so a claim about history
needs the changelog.** Before writing "was set", "was cleared", "the transition did X", or anything
else that places a change in time, read `…/issue/<KEY>/changelog`. Each entry in `.values[]` carries
`created`, `author.displayName`, and `items[]` of `field`, `fromString`, and `toString`, and the list
pages, so follow `isLast`. Never assert that one state caused another when nobody watched either
change happen. With no changelog to hand, say what the value is now and that you cannot see when it
changed. The rule comes from two confident claims about one issue's history, each inferred from its
current state, that both proved wrong.

**JQL search is `/rest/api/3/search/jql` only.** `/rest/api/2/search` and `/rest/api/3/search` both
answer `The requested API has been removed. Please migrate to the /rest/api/3/search/jql API`, and
piped to `jq` that error surfaces as `Cannot iterate over null` or a null total, which reads exactly
like a query that matched nothing. The replacement returns no `.total`, so never take a count from
it: iterate `.issues` and pass each `nextPageToken` back until none comes.

```bash
S=https://your-site.atlassian.net
# An issue's history (page with startAt until isLast is true):
curl -s --netrc "$S/rest/api/3/issue/PROJ-177/changelog" \
  | jq -r '.values[] | "\(.created)  \(.author.displayName)  "
      + ([.items[] | "\(.field): \(.fromString) -> \(.toString)"] | join("; "))'

# One page of a JQL search, then the token for the next page if there is one.
# Fetch the next page by adding  --data-urlencode 'nextPageToken=<token>'
curl -s --netrc -G "$S/rest/api/3/search/jql" \
  --data-urlencode 'jql=project = PROJ AND statusCategory != Done ORDER BY key' \
  --data-urlencode 'fields=summary' --data-urlencode 'maxResults=100' \
  | jq -r '(.issues[] | "\(.key)  \(.fields.summary)"), (.nextPageToken // empty | "next page: \(.)")'
```

**Read a custom field by an id you resolved from its name, never by one you typed or copied.** A
custom field is addressed by an opaque id, and reading the wrong id returns a confident `null` with no
error, so it reads as "this field is unset" instead of as a wrong question. A site can carry two
fields with near-identical names, one of them empty on every issue (Story Points is the common case,
in **Board and sprint operations**), and names are not unique, so treat more than one match as a stop,
not a pick.

**Then tell "unset" from "not on this issue's screen".** When the only field requested is
unavailable on the issue, Jira answers `200` with `id` and `key` and **no `fields` object at all**,
while a field that is simply unset comes back present with `null` (verified on two issues in 2026). A
genuinely unreadable issue returns `errorMessages` and no `key`, so discriminate on `key` first, never
on `fields`:

```bash
# 1. Resolve the id by name. More than one line back means the name is ambiguous: stop.
curl -s --netrc "$S/rest/api/3/field" | jq -r --arg n '<Field Name>' '.[] | select(.name == $n) | .id'

# 2. Read it, keeping the three answers apart:
F=customfield_XXXXX
curl -s --netrc "$S/rest/api/3/issue/PROJ-177?fields=$F" | jq -r --arg f "$F" '
  if (has("key") | not) then "UNREADABLE: \(.errorMessages // [] | join("; "))"
  elif ((.fields // {}) | has($f) | not) then "ABSENT: not on the screen for this issue type"
  elif .fields[$f] == null then "EMPTY"
  else (.fields[$f] | tostring) end'
```

**A field the screen refuses fails the whole call, so never batch it with other fields.** A PUT
naming a field that is not on the issue type's edit screen answers `HTTP 400`,
`Field '<id>' cannot be set. It is not on the appropriate screen, or unknown.`, and nothing else sent
in the same body is written either. Set a field you are unsure of in its own call and read it back.

**`/editmeta` cannot settle in advance whether that PUT will work.** It is the reflex on a 400, and it
gives a confidently wrong answer in the reassuring direction. Verified across three issues:
`GET /rest/api/3/issue/<key>/editmeta` on a **Story** did not list the Story Points field anywhere in
`.fields`, and the PUT set it anyway (`204`, read back correctly). On a **Bug** editmeta agreed with
the refusal, so the two sources match on one type and disagree on another, which means agreement
proves nothing either. This contradicts the general "check `/editmeta` first" advice. The only
reliable test is attempting the write against the issue type in front of you, on its own, and reading
the value back.

---

## Build a description as an ADF document, never as prose

**A description or comment sent as a plain string lands as a SINGLE ADF text node.** Blank lines and
`- ` bullets survive only as literal `\n` characters inside one paragraph, so the item renders as an
unbroken blob under a real person's name. Nothing signals it, because the flattened form is equally
valid ADF.

This bites harder than it sounds, because good practice for anything a system reflows is to write one
continuous line per paragraph with a blank line between, which is exactly the input that flattens.

Use [`jira-text-to-adf.py`](jira-text-to-adf.py), included here. It turns blank-line-separated text into
paragraphs, every `- ` or `• ` run into a `bulletList` with or without a blank line before it (a
numbered run still needs one), numbered runs into an `orderedList` that keeps your numbering, and every
`@[Display Name]` into a `mention` node. It emits the `{"fields": …}` payload the REST endpoints take,
so pass it unmodified:

```bash
# fix a description (PUT answers 204, no body)
python jira-text-to-adf.py body.txt --field description > payload.json
curl --netrc -X PUT https://your-site.atlassian.net/rest/api/3/issue/PROJ-510 -sS \
    -H 'Content-Type: application/json' --data @payload.json

# post a structured comment (POST answers 201)
python jira-text-to-adf.py note.txt --field body > payload.json
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-510/comment -sS \
    -H 'Content-Type: application/json' --data @payload.json
```

**Confirm a description by reading the ADF back:**

```bash
curl -sS --netrc "$S/rest/api/3/issue/PROJ-510?fields=description" \
  | jq -r '.fields.description.content | length, ([.[].type] | join(", "))'
```

More than one block, with `bulletList` where you wrote bullets, means it landed. A length of `1` means
you are looking at the flattened form. **Read it back on v3, never v2**:
`GET /rest/api/2/issue/<KEY>?fields=description` returns a plain-text rendering with the `\n`
separators intact, so a flattened description reads back looking properly paragraphed.

**A comment needs its own read-back, by the id the POST returned.** There is no field to re-GET, and
the obvious substitute is wrong: `…/comment?orderBy=-created` returns newest FIRST, so indexing the end
of that list hands you the OLDEST comment on the page. In the recorded case that returned a colleague's
comment from six days earlier and read as "the post did not land". Capture the id instead:

```bash
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-510/comment -sS \
    -H 'Content-Type: application/json' --data @payload.json -o posted.json
ID=$(jq -r '.id' posted.json)
curl -sS --netrc "$S/rest/api/3/issue/PROJ-510/comment/$ID" \
  | jq -r '.author.displayName, ([.body.content[].content[]? | .type] | join(", "))'
```

Check the author is who you expect, and that `mention` appears if you wrote one.

**`@`-mention somebody by writing `@[Display Name]`** in the input text and passing the converter
`--site your-site.atlassian.net` (or setting `JIRA_SITE`). It resolves each name through
`/rest/api/3/user/search` with the same `~/.netrc` token, keeps only **active** accounts whose
`accountType` is `atlassian` and whose `displayName` matches exactly (ignoring case), and **raises
instead of emitting plain text** when that leaves zero matches or more than one. Both filters are
load-bearing: a `qm:` customer account renders as nothing if its id is used, and a search by name
returns near-matches, so one person's full name can also return a colleague who shares the surname.
The brackets are required, because a display name contains spaces and a bare `@First Last` gives no
way to find where the name ends. A mention that survives the POST as plain text notifies nobody, and
the stored ADF is the only place that shows which of the two you got, so read the comment back.

**A comment or a field edit emails whoever the project's notification scheme names, so whom it
reaches is a per-issue question.** On the one project where this was checked, the Default
Notification Scheme named exactly the current assignee and all watchers for Issue Created, Issue
Updated, Issue Assigned, and Issue Commented, and never the reporter as such. Schemes vary, so check
yours, and answer the per-issue question with `GET $S/rest/api/3/issue/<KEY>/watchers`, never by who
filed the item. Two consequences: **`@`-mention the person you are replying to** on any comment,
because otherwise they hear about it only if they are the assignee or a watcher; and read the watchers
before a batch of field edits, so you know whom it emails.

---

## The `qm:` dual-account trap

On a site that also runs Jira Service Management, people commonly have **two** Atlassian accounts: a
JSM **customer** account (`accountId qm:…`, `accountType customer`, which **cannot be assigned
issues**) beside a real Jira **user** account (`accountId 712020:…`, `accountType atlassian`,
assignable). Where everybody has both, the duplicate is expected rather than a finding, so resolve
past it without comment. The case worth reporting is the reverse: someone with **only** a `qm:`
account, who can never be assigned. On a service desk project the customer account is the one that
raised the request, so it is the one you meet first there.

**Assigning or `@`-mentioning by email resolves to the wrong one** and fails with
`User '<qm:…>' cannot be assigned issues`.

**Resolve a candidate before proposing them as an assignee, not after.** Reasoning from who built
something in another system to a Jira assignee skips the question of whether they have an account at
all: in one recorded case the person proposed had no Atlassian account under any spelling, which one
search would have shown.

Resolve the `atlassian` accountId first, then assign by it:

```bash
S=https://your-site.atlassian.net

# 1. Resolve. Pick the entry with accountType atlassian and ignore any qm:/customer duplicate:
curl -s --netrc -G "$S/rest/api/3/user/search" --data-urlencode 'query=Jordan Lee' \
  | jq -r '.[] | "\(.accountId)\t\(.accountType)\t\(.active)\t\(.displayName)"'
#    Or scoped to who can be assigned on the project:
curl -s --netrc -G "$S/rest/api/3/user/assignable/search" \
  --data-urlencode 'project=PROJ' --data-urlencode 'query=Jordan Lee' \
  | jq -r '.[] | "\(.accountId)\t\(.accountType)\t\(.displayName)"'

# 2. Assign by accountId (204 = accepted):
curl --netrc -X PUT https://your-site.atlassian.net/rest/api/3/issue/PROJ-179/assignee -s \
  -H "Content-Type: application/json" --data '{"accountId":"712020:…"}'

# 3. Verify: confirm the name AND a fresh `updated` stamp
curl -s --netrc "$S/rest/api/3/issue/PROJ-179?fields=assignee,updated" \
  | jq -r '"\(.fields.assignee.displayName // "unassigned")  \(.fields.updated)"'
```

`@`-mentions in a comment are an ADF `mention` node carrying that same `atlassian` accountId. Read the
stored comment back and confirm the node survived, the same way you confirm a description.

---

## Board and sprint operations

```bash
S=https://your-site.atlassian.net
B=<boardId>
SPRINT=<sprintId>

# Active sprint for a board:
curl -s --netrc "$S/rest/agile/1.0/board/$B/sprint?state=active" | jq -r '.values[]|"\(.id) \(.name)"'

# A sprint's state (future, active, or closed) before you add to it:
curl -s --netrc "$S/rest/agile/1.0/sprint/$SPRINT" | jq -r '"\(.name): \(.state)"'

# Add an issue to a sprint (204 = ok; sub-tasks follow their parent automatically):
curl --netrc -X POST https://your-site.atlassian.net/rest/agile/1.0/sprint/$SPRINT/issue -s \
  -H "Content-Type: application/json" --data '{"issues":["PROJ-177"]}'

# Set Story Points via the board (200 = ok). Works whatever the screen carries, unlike a field PUT:
curl --netrc -X PUT https://your-site.atlassian.net/rest/agile/1.0/issue/PROJ-177/estimation?boardId=$B \
  -s -H "Content-Type: application/json" --data '{"value":"2"}'

# Which bucket a sprint's issues fall in (velocity counts completedIssues ONLY):
curl -s --netrc "$S/rest/greenhopper/1.0/rapid/charts/sprintreport?rapidViewId=$B&sprintId=$SPRINT" \
  | jq -r '.contents | {completed:.completedIssuesEstimateSum.text,
      elsewhere:.issuesCompletedInAnotherSprintEstimateSum.text}'
```

Find which field your board estimates on with
`GET /rest/agile/1.0/board/<boardId>/configuration | jq .estimation`. The Story Points custom field id
is per-site, so never copy one from documentation. Velocity per sprint comes from
`GET $S/rest/greenhopper/1.0/rapid/charts/velocity?rapidViewId=<boardId>`; read it live, since a
figure moves until the sprint closes.

**Per-person points from the sprint report need `currentEstimateStatistic`, never
`estimateStatistic`.** `estimateStatistic` is the estimate an item carried when it joined the sprint,
so anything pointed afterward counts as `0`, while the report's own `completedIssuesEstimateSum` uses
current estimates. Measured on one sprint, the at-join figures summed to 71 against the report's 85.
The per-person current figures should add up to `completedIssuesEstimateSum`, which is the check
(filter on `.typeName` first if your team counts only some issue types):

```bash
curl -s --netrc "$S/rest/greenhopper/1.0/rapid/charts/sprintreport?rapidViewId=$B&sprintId=$SPRINT" \
  | jq -r '.contents.completedIssues | group_by(.assigneeName)[]
      | "\(.[0].assigneeName): \([.[].currentEstimateStatistic.statFieldValue.value // 0] | add)"'
```

### Story Points: read the right field, and the PUT follows the screen

**A site can carry two estimate fields, and only one holds the values.** Jira Cloud ships a default
`Story point estimate` field, and a site can also carry a separately created `Story Points`. On one
site the board estimated on `Story Points` while `Story point estimate` was empty on every issue in the
project, so reading the default reported pointed items as unpointed, with no error. That wrong report
reached people four times in about two weeks despite written warnings, because a read has nothing to
check itself against, unlike a write you read back. Take the id from the board configuration or
resolve it by name (**History, search, and custom fields**). The tell, if a count looks impossible: a
JQL `"Story Points[Number]" is not EMPTY` returning issues whose field you read is uniformly `null`
means the field id is wrong, not the data.

A plain `PUT /rest/api/3/issue/<key>` naming the Story Points custom field succeeded on a **Story** and
was refused on a **Bug** and a **Sub-task** whose edit screens did not carry it, with:

```
Field 'customfield_XXXXX' cannot be set. It is not on the appropriate screen, or unknown.
```

**The refusal follows the edit screen, not the issue type.** After an admin added the field to the
Bug screen, the identical PUT on a Bug answered `204` and read the value back.

**Treat the per-issue-type answer as volatile and confirm it against the issue type in front of you.**
An earlier version of this note asserted the opposite for Story, verified two days before, and whether
the screen configuration changed or the earlier check was mistaken was never established.

**`/editmeta` UNDER-REPORTS this field, so it cannot be used to decide whether the PUT will work**
(the evidence is in **History, search, and custom fields**).

**The board estimation endpoint works regardless of screen configuration**, so reach for it whenever a
field PUT is refused. It is the only route for a sub-task, though a sub-task appears in no velocity
bucket at all, so where its work needs to count, point the parent.

**Never batch Story Points with other fields in one PUT.** A screen refusal answers `400` and writes
none of the other fields sent alongside it, so set it in its own call and read it back.

### Velocity cannot be back-dated in either direction

A **completed** sprint refuses any new issue, both routes: `You must specify a sprint which has not
been completed.` from the agile API, and `Issue can be assigned only active or future sprints.` from a
field PUT. Verified against two different closed sprint ids, so it is a platform rule rather than a
workflow quirk.

Moving the work into the **active** sprint does not credit it either: an item that reached Done before
the sprint opened lands in `issuesCompletedInAnotherSprint`, which the velocity chart excludes.
Measured on one sprint, three items carrying 3 points sat in that bucket while `completedIssuesEstimateSum`
stayed at 19. The only mechanism that would move them is reopening and re-closing inside the sprint,
which misdates when the work shipped.

**So raise a missing sprint assignment promptly rather than late — the window is one-way.**

---

## Closing an issue with a specific resolution: the transition cannot carry it

**`resolution` cannot be set through a transition, and batching it into the transition POST rejects the
whole call.** Verified closing a Bug as a duplicate: a transition POST carrying
`{"fields":{"resolution":{"name":"Duplicate"}}}` answered **`HTTP 400`**, `Field 'resolution' cannot be
set. It is not on the appropriate screen, or unknown.`, and **the issue did not move**. That atomic
refusal is the good failure mode, since a partial success would have closed the issue carrying the
wrong resolution.

Check whether any transition on your workflow exposes fields at all before hunting for another one:
`GET /rest/api/3/issue/<key>/transitions?expand=transitions.fields` returned an empty `fields` object
for every transition on the workflow measured.

**The working shape is two calls: transition first, then `resolution` as its own atomic field PUT.**
Both answer `204`, verified on a bug and on a sub-task:

```bash
# 1. move it (read the id live first, as in "Common operations")
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-695/transitions -s \
  -H "Content-Type: application/json" --data '{"transition":{"id":"<done-id>"}}'
# 2. correct the resolution, on its own
curl --netrc -X PUT https://your-site.atlassian.net/rest/api/3/issue/PROJ-695 -s \
  -H "Content-Type: application/json" --data '{"fields":{"resolution":{"name":"Duplicate"}}}'
```

**A bare transition to Done auto-sets resolution `Done`, so the second call is a CORRECTION rather than
a first write.** Skipping it leaves a plausible-looking `Done` on an issue you meant to close as
`Duplicate` or `Won't Do`, and the transition's own `204` says nothing about it. Read the resolution
back. Your project's values come from `GET /rest/api/3/resolution`.

---

## Linking a duplicate, and reading any link back

**The issue that IS the duplicate goes in `inwardIssue`.** `GET /rest/api/3/issueLinkType` gives
`Duplicate` as `outward="duplicates"` and `inward="is duplicated by"`, and the **inward** issue is the
one that displays the outward description:

```bash
curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issueLink -s \
  -H "Content-Type: application/json" \
  --data '{"type":{"name":"Duplicate"},"inwardIssue":{"key":"PROJ-695"},"outwardIssue":{"key":"PROJ-680"}}'
```

which reads `PROJ-695 duplicates PROJ-680` from one side and `PROJ-680 is duplicated by PROJ-695` from
the other.

**Swapping the two answers `201` just the same and records the opposite claim.** Alongside a
`Duplicate` resolution on the closed ticket, that says the *surviving* ticket is the copy, which is
worse than no link at all. Nothing errors either way, so the only way to catch it is to read the link
back from both sides.

**There is no flip operation: fix a reversed link by deleting and recreating it.** Take the `.id` off
the issue's own `issuelinks`, `DELETE /rest/api/3/issueLink/<id>` (answers `204`), then POST the
reverse.

**Reading a link back needs a direction-aware `jq`, and the obvious shape is silently wrong.**
`.type.outward // .type.inward` takes `outward` whether or not this issue is the outward side, so an
**inbound** link renders as its own opposite. In the recorded case that printed `blocks PROJ-693` for a
link that actually said `is blocked by PROJ-693`, and the inverted reading was stated as fact and acted
on, which reversed the order two pieces of work had to happen in. Branch on which key is present, and
print the link id, which is what a delete-and-recreate needs:

```bash
curl -s --netrc "$S/rest/api/3/issue/<KEY>?fields=issuelinks" | jq -r '.fields.issuelinks[]
  | if .outwardIssue then "\(.id)  \(.type.outward) \(.outwardIssue.key)"
    else "\(.id)  \(.type.inward) \(.inwardIssue.key)" end'
```

**The changelog states a link's direction in Jira's own words, so settle any doubt there.** It records
each link as `field: "Link"` with the sentence in `toString`, such as
`This work item relates to PROJ-364`, and a removed link reads with a `null` `toString`. Another
issue's existing link is no evidence of the convention: one existing link was found contradicting its
own issue's description, so copying from it would have reproduced the error.

A Jira Product Discovery idea reaches a delivery project through the link type
`Polaris work item link`, where the idea *is implemented by* an epic there, so expect that name when
reading links on an epic that came from an idea.
