---
name: qa-handoff
description: "Creating and handing off a QA sub-task in Jira for Salesforce work. TRIGGER when: writing QA test steps, creating a 'QA:' sub-task, capturing QA screenshots, assigning a tester, moving a story or bug to a QA status, posting a handoff, or QA failing on the sandbox rather than the change. Not for clearing QA, which an independent tester does."
metadata:
  version: "1.1"
  license: MIT
---

# qa-handoff

Writing a QA sub-task a tester can act on without you, and handing it over without tripping the
automation on the way.

Assumes Jira with `Build:` and `QA:` sub-tasks under a story or bug, and a Salesforce org the tester
signs into. The step-writing craft transfers anywhere; the Jira mechanics are specific to that setup.

**The one rule that is not negotiable: QA is cleared by somebody other than the builder.** Read-only
verification to tee QA up does not count as clearing it, and neither does the person who wrote the
change signing it off.

Point-in-time: measured during 2026. Verify anything volatile against your own instance.

---

## Before you write anything

- **Check whether the QA sub-task already exists.** A Jira automation rule commonly creates `Build:`
  and `QA:` sub-tasks on issue creation. Amend the existing one rather than adding a second, because
  a gate that aggregates every QA sub-task on the key now has two lanes to satisfy.
- **A change to what a story already SHIPPED gets its own work item, never a second QA sub-task on the
  closed story.** Once a story is `Done` it is a historical record. File a **Bug** if the shipped
  behavior is wrong, a **Story** if the requirement changed, link it to the original rather than
  parenting under it, and key the branch off the new item. Attaching the change to a `Done` story
  loses the tester's start signal and leaves a closed ticket describing behavior that is no longer
  live. While the story is still open the opposite applies: amend in place, same key.
- **Confirm the tester can actually log in to the target org.** Having a user there is not having
  access. Query `LastLoginDate` and `Email` alongside the profile check, since a sandbox refresh
  appends `.invalid` to every address and a user can be active, correctly profiled, and locked out.
  If they are, change the org or hand it over rather than editing their account.

---

## Writing the steps

### Summary line

`QA: <what to verify> (<PARENT-KEY>)`

Start with `QA:` so it matches a start-anchored pattern like `^QA\b` if a merge gate reads sub-task
summaries. **Append the parent key rather than prefixing it**, so the anchor still matches, and the
sub-task stays self-identifying in notification emails, on mobile, and in flat search.

### One check per number

**The testing guidance is a numbered list, one check per number.** The numbers are what the tester
records pass, fail, and findings against, so paragraphs, bullets, or several checks folded into
one step all leave them nothing to anchor a result to.

Each step is one action plus the result that counts as a pass. Anything that is not a check, such as
setup context or the target-org callout, sits outside the numbering.

### Give the field combination, not test record Ids

**This is the single most useful rule here.** Naming specific records looks concrete and is the more
fragile choice: those are live business records, somebody moves them, and the step becomes untestable
with nobody noticing. In the recorded case all three records named in one sub-task drifted within
three days.

State the criteria the component or automation keys off, in page-facing labels, so the tester can find
a current record themselves. Cite a record as a convenience example if you like, but the criteria are
the instruction. Best of all is a test record the **tester themselves owns**.

The same drift hits your own re-verification. And **a record you cite should still isolate the fix**:
check the other criteria have not shifted to hide the behavior for an unrelated reason, or a passing
result proves nothing.

### Page-facing labels, verified live

Name every object and field by the **label shown on the tester's record page**, not the API name and
not a logical name you assumed. Verify with a live `sf sobject describe`. A label mismatch reads to
the tester as a missing field and produces a false QA gap.

**Before naming a field in a step, confirm a page actually renders it.** A field can exist on the
object, with the right label, and render on no page at all, and the tester then reads a correct step
as a missing field. On a Dynamic Forms page, search the FlexiPage source for
`<fieldItem>Record.<Field></fieldItem>`, then open the tab it sits on. In the recorded case two fields
had zero `fieldItem`s on any page, one of them appearing only as a component's visibility criterion.
Key such a step off a signal the tester can see instead (a status field reading a particular value,
an action appearing in the header), or have them confirm the value through a list view filter, which
field-level security allows where no page shows the field.

### A field taken off a page needs a step that fills it in

**When a story or bug takes a field off a record page, add a step that runs each action needing that
field on a record where it is blank.** Taking a field off a page can remove the only place to fill
it in, and nothing errors until someone runs an action that a flow guards. The deploy is green, and a
step confirming the field is gone passes. A copy of the field in the highlights panel does not count:
it shows the value but cannot edit it.

To find the actions, search your flow source (`force-app/main/default/flows/` in a default project)
for the field's API name, then follow each match up to the flow a person actually launches, because
the check often sits in a subflow that sets an output the parent turns into an error screen. Confirm
each of those flows is active in the QA org (`FlowDefinitionView`) before writing its step.

In the recorded case a story took a field off a child section of a record page as asked, its QA
confirmed the field was gone, and no step filled it in or submitted a child record. The first sign was
a user blocked from submitting a record for approval a few days after the release.

### An approval that must stay open needs a second approver

If a step needs an approval round still open after a first approval, plan a second, distinct
approver. Check how your approval design assigns work first: a design that dedupes approvers by user
gives a person holding several approver roles one work item, and approving it decides every role
they hold at once, closing the round the step meant to leave open.

Do not fill the second slot with an integration or admin user. One that has never logged in, with an
`.invalid` email address, receives no notification, and in the recorded case its work item stayed
open until the submission was recalled (seen once, not re-tested). A System Administrator profile
also tests nothing that depends on the approver's permissions.

### Name the org, and say why when it is not the usual one

**Default to the shared QA sandbox your testers can actually reach, and treat any other org as the
thing needing a reason.** Reaching for an exception on a story it does not apply to strands the
tester. A developer's own sandbox is nobody's QA org by default: a colleague can be active there with
the right profile and never have logged in, for example where single sign-on covers only production
and the shared sandbox, and a refresh appends `.invalid` to every address. Before naming any other
org, run the login check from **Before you write anything**.

Two exceptions are real, and the second is narrower than it first reads.

**A fix that only exists in production has to be QA'd in production.** A tester who exercises it in a
sandbox gets a **false pass**, because the change is not there.

**A change that grants access to a field the QA sandbox already grants tests nothing there.** A
sandbox's profile can carry far more field grants than the same profile in production: measured on
one profile at 1,358 field grants in the sandbox against four in production. Newly granting an
existing field then makes no observable difference in the sandbox, and the tester signs off having
verified nothing. **It never applies to anything the story creates.** A new object, field, or custom
metadata type has no prior grant in any org, so nothing can mask the check and the shared sandbox
tests it honestly. Query `FieldPermissions` for the specific field in both orgs before concluding
otherwise. The difference also runs the other way, the sandbox being more restrictive than production
in places, so either way a result can be about the org rather than about the change.

Put the org in the steps as an explicit callout rather than an aside. If your team's default
assumption is a particular QA sandbox, silence reads as "test there."

---

## Exercise every path before you write about it

Click through each new or changed user-facing path end to end: each screen, each branch, as the
persona who will actually use it, with `Login As` for a second persona.

**The screenshot is the byproduct of that run, never the deliverable.** Capturing one proves a field
renders; it does not prove the feature works. In the recorded case a record-page capture read as the
requirement met while neither of the story's two screen flows had been opened, and running them found
three defects past a clean 188-component validation, including that nobody could approve anything.

---

## Screenshots

### Place each one at the step it illustrates

**Attaching is not placing.** A file the tester has to match up against a step themselves looks like
compliance and is not, which is exactly how a gap slips through. Placement puts visual acceptance
criteria at each step.

Producing it is also what puts the builder in the UI, which is the only place a user-visible symptom
is confirmed fixed. One fix was confirmed by SOQL while the tab the user had complained about still
showed the old state; opening the tab is what caught it.

**An image can sit inline at the step from the REST API, through an `external` media node.** An
earlier version of this skill said Jira's REST API could not embed an image inline at all. That was
wrong; the narrower finding about `file` media nodes, in this section, is what survives.

Upload with `POST /rest/api/3/issue/<key>/attachments` (header `X-Atlassian-Token: no-check`), which
returns a numeric attachment id. Then, immediately after the step, put an ADF `panel` naming the exact
filename and what it shows, followed by a `mediaSingle` pointing at the attachment's own content URL:

```json
{"type":"mediaSingle","attrs":{"layout":"center"},
 "content":[{"type":"media","attrs":{"type":"external",
   "url":"https://<your-site>.atlassian.net/rest/api/3/attachment/content/<id>"}}]}
```

The URL is same-origin, so the viewer's own Jira session authenticates the image. The panel is the
caption and the image sits under it. This was verified by looking at the rendered page rather than at
the `204`, for one signed-in user; that every user with access to the issue sees it too is inference.

- **A `file` media node is not reachable from REST.** It needs a Media Services UUID, which the browser
  editor's own upload produces and the attachment API never returns. A `media` node built from the
  numeric attachment id is rejected with `400 ATTACHMENT_VALIDATION_ERROR`, and the `mediaTokens`
  endpoints tried returned `404` on the site measured. A rejected media node fails atomically, so it
  leaves the description untouched rather than half-written.
- **The `external` node is a URL reference, not an embedded object**, so deleting the attachment
  breaks the image.
- **Crop a full-page capture before attaching.** One record-page capture carried about 400px of empty
  card, which renders as a long blank gap in the description.

**Consecutive `orderedList` nodes restart at 1**, so a panel or image splitting your numbered list
silently renumbers everything after it. Set `attrs.order` on each following list and read the
numbering back. Inserting a `panel` or `mediaSingle` between two lists does not disturb `order` values
already set. Check the numbering in the stored ADF's `order` values or on the Jira page, never in
`renderedFields`, whose HTML drops the `start` attributes so every list reads as beginning at 1.

### Two captures per changed screen: desktop and phone

Anything rendering on a record page, an app page, or a home page — an LWC, a field on a layout, a
quick action, a screen flow — has to be shown working on a phone as well. Mobile failures deploy
clean, error nowhere, and reach you as a person saying they cannot do something from their phone
rather than as anything you can query.

**When the change genuinely has no mobile surface, write that line into the sub-task** rather than
leaving the capture out, so the tester reads a decision instead of a gap.

### The phone capture needs no phone

Take it from **Lightning App Builder's phone view**, which runs in an ordinary desktop session,
renders the record page at the phone form factor, and names any component the phone will drop. Get the
FlexiPage id from a Tooling query, then open the App Builder URL and switch the preview device:

```
/visualEditor/appBuilder.app?id=<flexipage-id>
```

A desktop-only component draws a grey **Unsupported form factor** bar naming itself, which is how you
catch an LWC that is simply absent from the mobile app before a user reports it.

**Emulating a phone in the browser does not work.** Measured in two orgs: a mobile-emulation session
is redirected to Salesforce Classic from the frontdoor URL, from a Lightning record URL, and from
`/one/one.app` alike, while the identical sequence in a desktop session reaches Lightning. **Why was
not established**, so read it as observed behavior rather than a settled rule and re-test if it
matters.

**A real phone is only needed when the step is about the feature working on the device** rather than
about a component being present: a screen flow completed by touch, an approval actually cast. Then the
tester captures in the mobile app themselves.

### Capture mechanics

**Capture with whichever browser already reaches the org; both routes produce a file to upload.**
An earlier version of this skill preferred a headless browser over a signed-in one. Either works for
capture now, because the Claude in Chrome extension's captures leave a file too, which older Claude
Code builds did not.

**A signed-in browser, through the Claude in Chrome extension.** Every screenshot or zoom result ends
in an `[Image: source: <path>]` line naming a file Claude Code saved under the session's
`tool-results` folder (`~/.claude/projects/<project>/<session-id>/tool-results/`), and that file is
what you upload. A screenshot with `save_to_disk` and one without came back as byte-identical files,
so the file is Claude Code keeping the image the tool returned and `save_to_disk` adds nothing. A
screenshot is a JPEG of the visible window; `zoom` returns a PNG of one region. Copy the file to a name
that says what it shows before uploading, since Jira displays the filename. On one machine, sessions
through Claude Code 2.1.281 saved no file and every session from 2.1.284 did, so if a capture comes
back without the `[Image: source: ...]` line, take the file headless instead.

**A headless browser, when no signed-in browser reaches the org.** A frontdoor URL
auto-authenticates, so it needs no SSO and no MFA handoff:

```bash
FD=$(sf org open --target-org <qa-org> --url-only --json | jq -r '.result.url')
HOST=$(echo "$FD" | sed -E 's#^(https://[^/]+)/.*#\1#')
```

The frontdoor URL carries a one-time session token, so keep it out of logs and transcripts. If your
browser driver echoes the URL it opened (`playwright-cli open` does), filter its output down to the
page it landed on.

Three things that each cost a wasted capture:

- **The frontdoor URL is single-use.** Open it once to establish the session, then navigate by path.
- **Resize to something like 1600x1200 first**, or a record page's lower half is cut off. Check the
  field under test is in frame anyway: at that size one record page still had it below the fold. A
  full-page capture avoids that and needs cropping before it is attached.
- **Reach Lightning checkboxes and buttons through `getByRole`**, which pierces the shadow DOM, and
  allow 15 to 20 seconds for the page to settle.

**In an org with SAML single sign-on, a frontdoor attempt can land on the identity provider's sign-in
page instead of Lightning.** Seen once: one attempt landed on the identity provider and another 15
minutes later reached the Lightning home page, while the org logged a successful `OAuth OTP Login`
for each and no MFA challenge. The cause was not established, and it is not a standing block. Retry
once with a fresh frontdoor URL in a new browser session, and if that lands on the identity provider
too, capture from the signed-in browser.

**To run a path as another user headless, Login As goes through the servlet after the frontdoor.**
Once the frontdoor has established the admin session, take the org Id from
`SELECT Id FROM Organization` and navigate to:

```
$HOST/servlet/servlet.su?oid=<orgId>&suorgadminid=<userId>&retURL=%2F&targetURL=<url-encoded Lightning path>
```

The servlet handshake is required: in an org with single sign-on, a direct Lightning URL bounced to
the identity provider. Before capturing anything, confirm whose session you are in with
`fetch('/services/data/v<NN>.0/chatter/users/me')` from inside the page, and open records under
`/lightning/r/<Object>/<id>/view`, since FlexiPage and dynamic-action buttons render only in
Lightning.

**Set up as much as possible through the API so the browser only does what must be seen.** An
error-path capture needs a real save attempt, but the record it acts on can be created by
`sf data create record` in the state that leaves one field to change. Grant the viewing user FLS on
any new field first so it renders, then revert.

**Never invent a URL, path, or identifier as test data.** A made-up value written into a sandbox
record and its QA screenshots reads to the tester as a genuine example and points at nothing. Ask for
a real value, leave the field empty, or label the value plainly as a placeholder, and check your
source first, since real hosts and paths often already sit in committed components.

---

## Handing it over

**Assign the tester when you create the sub-task. The parent's status is what gates them.** Testers
know not to start a QA sub-task until its parent reaches the QA status, so an assignment on a sub-task
whose parent is still `To Do` is a queue entry rather than a request to begin. Do not hold the
assignment back on the reasoning that the change is not testable yet.

### The two automation rules that pull in opposite directions

Knowing only one of them produces the failure the other was meant to prevent.

- **A rule transitions a parent to `Done` once every sub-task is Done.** On a story whose only
  sub-task is the `Build:` one, finishing the build sends the parent to `Done` with
  `resolution=Done` instead of to QA.
- **A rule reverts a parent moved INTO the QA status while a `Build:` sub-task is not Done.** Measured
  once at two seconds: the parent reached the QA status at 01:44:22 and was put back at 01:44:24.
  **The trigger is that transition, not the existence of an open `Build:` sub-task.** A `Build:`
  sub-task created against a parent already in the QA status, and left open well past that revert's
  timing, did not disturb it, and the parent's changelog carried no automation entry. An earlier
  version of this skill described the rule as a standing condition, which produces a confident warning
  against a safe operation. Check your own rule's trigger rather than inferring it from its effect.

**So the working order is: create the `QA:` sub-task, then move the `Build:` one to Done, then move
the parent.** Creating the QA sub-task first leaves one open, so the first rule does not fire.
Moving the parent first simply does not stick.

Recovery from a false `Done` does work, since transitioning to the QA status clears the resolution,
but it costs a `Done` that stays in the changelog for good plus a status notification to every
watcher. **Ordering is the whole fix, so do not reach for the recovery.** If the QA sub-task is not
ready to write yet, that is a reason to ask before finishing the build sub-task, not a reason to
proceed and correct afterwards.

### Post the handoff as a comment on the ticket

Scenarios, target org, screenshots, and who should test, as a comment on the story or its QA sub-task,
with an `@`-mention of the tester, so it lives with the work and they are notified where they track
it. Do not compose it as chat text for somebody else to paste.

A mention is an ADF `mention` node carrying the assignable account id, which on a site also running
Service Management is not the one an email lookup returns.

### Verify it landed

Read every write back through REST rather than off a status code. A `204` says the call was accepted,
not that it wrote what you meant, and a flattened description is equally valid ADF.

**Wait about 20 seconds before reading back a transition.** A read fired a second or two after one can
return the pre-automation state: the `GET` is truthful and already stale, which is how a reverted
transition was first reported as a success. Where you need to know what actually happened, prefer the
changelog over the current status.

---

## When QA fails on the org rather than the change

- **Check drift between the QA org and the branch before reworking the change.** And check for an
  open pull request before calling a difference drift: a component deployed to the QA org for testing
  while its pull request is still open is legitimately newer there.
- **When the QA sandbox is stricter than the change explains, compare the active validation rule
  sets.** A deactivation that reaches production through source never reaches the sandbox unless
  someone deploys it there, so a QA failure can belong to the org. List the org's active rules with a
  Tooling query, compare them against the source rules carrying `<active>true</active>`, and read one
  rule's formula through a single-record Tooling query on `ValidationRule.Metadata`, since a query
  returning more than one row cannot return `Metadata`:

  ```
  SELECT ValidationName, EntityDefinition.QualifiedApiName FROM ValidationRule WHERE Active = true
  ```

- **Flow activation is a separate check** that no rule comparison covers (see
  `salesforce-flow-versions`).
- **A field-permission difference between the orgs** can hide a change or cause a failure the change
  did not, as **Name the org, and say why when it is not the usual one** describes.

---

## Drafting is not posting

Assignment, the transition, and the handoff comment all land in a system under a real person's name.
Each is an outward action needing its own go-ahead from whoever is directing the work, and approval of
the **content** is not approval to **post** it.
