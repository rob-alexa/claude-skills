---
name: salesforce-flow-versions
description: "Salesforce Flow VERSIONS and activation: which version an org is really running, and why a deployed flow is not a live one. TRIGGER when: a flow deployed but its fix is not live, a version reads InvalidDraft, every deploy of a flow failing 'insufficient access rights on cross-reference id', activating or deactivating a flow, deciding whether a flow is dead, deleting a flow or a field a flow references, comparing an org's flow against source, an org behaving like an older version of a flow, or a running orchestration keeping stages that no longer exist. Not for a flow defect that renders wrong on screen."
metadata:
  version: "1.1"
  license: MIT
---

# salesforce-flow-versions

Which version of a flow an org is actually running, and why almost nothing you can read from source or
from a deploy result answers that.

**The shape every item here shares: a version is a separate object from the flow, and the tools all
report on a different one than you assume.** Source reports intent. A deploy result reports the
component. A retrieve reports the **latest** version. `FlowDefinitionView.IsActive` reports the
**active** one. Reading any of them as the others is where the wrong answers come from.

Point-in-time: measured on Salesforce orgs during 2026, API v66.0. Verify against your own org before
asserting any of it as current fact.

---

## The queries worth having before anything else

```sql
-- every version of a flow, with its status  (Tooling API)
SELECT Id, VersionNumber, Status, CreatedDate FROM Flow
  WHERE Definition.DeveloperName = '<ApiName>' ORDER BY VersionNumber DESC

-- which version is ACTIVE  (standard API)
SELECT ApiName, ActiveVersionId, IsActive FROM FlowDefinitionView WHERE ApiName = '<ApiName>'
```

```bash
# the content of ONE specific version (Metadata is not queryable through SOQL)
sf api request rest "services/data/v66.0/tooling/sobjects/Flow/<301...>"
```

Three gotchas on those:

- **`FlowDefinitionView` is not supported with `--use-tooling-api`** and answers
  `INVALID_TYPE: sObject type 'FlowDefinitionView' is not supported`. Use the standard API.
- **A flow absent from the org returns no row rather than a null**, so compare the row count against
  the names you asked for, or an absence reads as an inactive flow.
- **The Tooling `Flow.Metadata` field is retrievable one row at a time only** (`WHERE Id = '...'`). An
  `IN (...)` errors with *"must specify no more than one row"*.

---

## A deploy to production lands every flow inactive

Whatever tool deployed it. This is not a quirk of one pipeline: it holds for a managed deploy tool with
no activate-on-deploy setting at all, and for a direct `sf project deploy quick` run by a human
administrator, including flows whose source said `Active`.

**So every release needs a post-release activation step**, and the safe pipeline shape is
deploy-inactive-then-activate. Production also requires at least 75% flow-test coverage to deploy an
*active* record-triggered, scheduled, or autolaunched flow, which is a second reason to ship inactive.

**Activate an already-deployed version without creating a new one** by deploying a `FlowDefinition`
file carrying `<activeVersionNumber>N</activeVersionNumber>`. A CI service account often cannot do this
(activation needs View All Data, which a deploy-only account should not have), so it is usually an
administrator's step.

### Do NOT blindly bulk-activate everything inactive

Cross-check each flow's **source** `<status>` first, because it encodes intent that the org's inactive
state does not. One naive "activate all 40 latest-inactive" wrongly turned on three flows and had to be
reverted.

| Source status and type | Meaning | Action |
|---|---|---|
| `Active` + record-triggered | Meant to be live | Activate |
| `Draft` + record-triggered or autolaunched | Staged, not ready | Do **not** activate |
| `Draft` + scheduled, or a screen flow needing per-org setup | Shipped Draft by convention, because the CI account cannot activate it | Activate per org |
| `Obsolete` | Retired | Never activate |

**Also exclude flows that are inactive because somebody deliberately turned them off.** Search your
tracker for the flow name to catch an open bug, and treat a first-time activation whose production
history already contains an `Obsolete` version as a prior deliberate off-switch rather than a missed
deploy.

**Watch what a batch activation actually starts.** A scheduled flow begins running the moment it is
activated.

**A scheduled flow runs as the org's Default Workflow User (Setup, Process Automation Settings), not
as whoever activates it.** So read who that user is, and what custom permissions they hold, before
activating one: those decide what validation rules and bypass-guarded automation do on every run. The
other reading is easy to arrive at, because the scheduled job's `CronTrigger` is owned by the account
that activated the version. Measured in one production org: the `CronTrigger` jobs of four scheduled
flows were owned by their activators, while the records those runs created and updated were last
modified by the Default Workflow User. Whether a run survives deactivating the job's owner is not
established.

**A large production deploy can outrun a two-minute tool timeout.** The local `sf` is killed while the
server-side deploy keeps going. Recover with `sf project deploy report --use-most-recent --json`, then
`sf project deploy resume --job-id <id> --wait N`. `resume` takes no `-o` flag, since it uses the
cached job's org. Never re-submit, or you double-deploy.

---

## A flow's source `<status>` does not indicate whether it is live

**`<status>Draft</status>` in a tracked flow file is not evidence the flow is dead.** Measured against
one production org: of the nine flows whose source said Draft or Obsolete, **six were ACTIVE in
production**.

| Source status | Production state | Count |
|---|---|---|
| Draft | **ACTIVE** | **6** |
| Draft | inactive | 2 |
| Obsolete | absent from every org | 1 |

**Why:** a production deploy lands every flow inactive, an administrator activates it in the org
afterwards, and the source status is never reconciled back. So source drifts to Draft permanently while
the flow runs. Scheduled and always-system-context flows are additionally shipped Draft on purpose.

**Before retiring, deleting, or counting "dead" flows, check the org, not the file.** In the recorded
case a tech-debt document had listed the source-Draft flows as retirement candidates, and acting on it
would have deleted working automation.

---

## After a release, compare latest-against-active for every flow in the payload

**An activation checker that flags only flows whose source ships `<status>Active</status>` cannot
detect the most common missed activation, and it reports the org CLEAN while it happens.** Most flows
sit at `Draft` in source for the reason above, so they are invisible to such a check by construction.

Measured the day after one release: the payload carried **16** flows, the checker answered *"all
source-Active flows are active"*, and **4 of the 16** were still running their previous version. Two of
those backed items that had already been announced to the whole company that morning, so the release
notes described behavior that was not live.

**`FlowDefinitionView.IsActive` will not answer this.** It reports on whichever version is active, so
it reads `true` while the newly deployed version sits Draft. Take the `Flow` members straight out of the
release manifest and compare per name:

```bash
sf data query --use-tooling-api -q "SELECT Definition.DeveloperName, VersionNumber, Status FROM Flow WHERE Definition.DeveloperName IN (...) ORDER BY Definition.DeveloperName, VersionNumber"
```

Then group by name and assert `max(VersionNumber).Status == 'Active'`.

**Diff two flow versions with the Tooling API, not a retrieve**, since a retrieve returns only the
latest. Query `SELECT Metadata FROM Flow WHERE Id = '<301...>'` one row at a time, compare the `name`
sets per element collection (`assignments`, `decisions`, `formulas`, `recordLookups`) to see structural
change, then compare same-named elements field by field to see repoints. That is what distinguished a
two-step subflow repoint, safe to activate immediately, from a full routing rewrite that was held back
deliberately at the time and activated later.

---

## Deactivation: a Draft deploy is not an off-switch

**Deploying the Flow with `<status>Draft</status>` does NOT deactivate an already-active version.** It
adds a new inactive version while the active one keeps running and firing.

To actually deactivate, deploy a `FlowDefinition` file with `<activeVersionNumber>0</activeVersionNumber>`
at `force-app/main/default/flowDefinitions/<Name>.flowDefinition-meta.xml`. The artifact does not need
to be committed: build it in a scratch directory and deploy that directory.

A *fresh* deploy of `status=Draft` to an org that lacks the flow does land it inactive at v1, which is
fine for shipping inactive to production. The two cases look identical in source and are not.

Worked example: a before-save validation flow was switched off in production with a `FlowDefinition`
deploy, and the source change recording that set its `<status>` to `Draft`. In one sandbox the
pipeline deployed the merged change 46 seconds after the merge, as a new Draft version, and
deactivated nothing. The
flow kept enforcing its rule in two sandboxes for 58 days after its removal was requested, until each
was turned off with its own one-component `FlowDefinition` deploy. **Switching a flow off is per org,
and so is confirming it:** query each org's active version, and where one is active, fetch that
version's body to confirm it is the behavior you mean, rather than trusting its status alone.

**`FlowDefinitionView` LAGS after the deploy, so do not use it to verify.** `IsActive` and
`ActiveVersionId` can keep showing the flow active, with the old `ActiveVersionId`, for several minutes
after a deactivation deploy has already reported Succeeded. Verify against the Tooling
`FlowDefinition.ActiveVersionId` (null means inactive) or per-version `Flow.Status`. Those go fresh
immediately.

**Once a flow has been deactivated, a later content deploy of Active-status source lands INACTIVE.**
Reactivation always needs its own explicit `FlowDefinition` step; the deploy never restores it for you.

**A flow deploy reporting `changed=false` can still have created a real new active version.** Never
trust the deploy's `changed` flag for flows. Query the versions.

---

## `InvalidDraft`: three routes to a green deploy that cannot be activated

`InvalidDraft` is distinct from `Draft` and shows only in a Tooling query on `Flow.Status`. Attempting
activation gives *"You can't activate version N of this flow because it has errors"*, which names
nothing. **So check the version's Status after deploying a flow, rather than reading the deploy
result.**

**Isolate any `InvalidDraft` the same way: deploy the UNMODIFIED file first and see which status it
lands in.** That separates "my edit broke it" from "this flow was already invalid".

In the measured cases of the first two routes, the `InvalidDraft` version could still be read and
overwritten. A missing **object** leaves one that cannot, which is a different case with a different
fix: see the section *An `InvalidDraft` that cannot be read, deleted, or deployed over*.

### 1. The target org lacks a field the flow reads

**Salesforce does not fail the component.** It silently rewrites the unresolved merge reference to the
literal placeholder **`null__NotFound`** and marks the new version `InvalidDraft`. The deploy reports
the flow in `componentSuccesses`, so nothing in the release output hints at it.

Live case: a flow deployed in a 105-component, zero-error release and landed `InvalidDraft`. The org's
stored copy read `<assignToReference>varSuggested.null__NotFound</assignToReference>` where source read
`varSuggested.Example_Lead__c`, and the same for a second field. Root cause was an incomplete
capture: the flow shipped alongside 14 discipline configuration records against only 11 matching lead
fields, and two of the fields existed in no org and in no source.

**Diagnose by retrieving the org's stored flow and diffing it against source.**

```bash
sf project retrieve start -m "Flow:<Name>" --output-dir <dir>
```

The `null__NotFound` tokens name the broken references directly. **This is the only step that gives a
straight answer.** Extracting field references from the source XML and checking each against the org
found nothing, because the references that mattered were on a **flow variable** rather than inside a
`recordLookups` or `recordUpdates` block or a `__r` traversal, so a scan of those element types misses
them entirely.

**Do not conclude the flow is fine elsewhere because another org reports Active.** One org read
`IsActive=true` while its latest version was `InvalidDraft` with byte-identical `null__NotFound`
content; it was simply still running an older version.

**One error string has accompanied a missing field in every logged case, though Salesforce does not
document its cause.** A deploy or activation error reading *"The type for the input parameter
"<name>" doesn't match the type for the assigned value."*, sometimes wrapped in `field integrity
exception: unknown (...)`, names neither a field nor an object. In each of three logged cases the
named input was bound to a field the target org lacked: the two lead fields in the live case in this
section, a lookup field in a check-only deploy to a sandbox, and a custom metadata field in another
sandbox. That pattern is inference from those logs. So check the fields the named input is bound to
before treating it as a flow defect. That missing field-level security produces the same message rests
on one observation and is unconfirmed.

### 2. A subflow's new input variable, deployed in the same payload

One deploy carried a subflow gaining a new input and an orchestration passing that input to it. The
deploy reported `status: Succeeded`, `numberComponentErrors: 0`, every component in
`componentSuccesses`, and left the orchestration `InvalidDraft`. Re-deploying **only** the
orchestration, with the subflow already active, turned that same version into plain `Draft`, which then
activated normally. No new version was created by the second pass; a Draft is overwritten in place.

**The compile-order explanation is inference, not proven.** The only thing that changed between the two
deploys was that the subflow's new input already existed; it was not isolated further.

It is the same shape as other two-pass bootstraps: a payload cannot always resolve a reference to
something else in its own payload.

### 3. `$GlobalConstant.EmptyString` used to clear a field

Clearing a Long Text Area field that way compiled to `InvalidDraft`; an empty
`<stringValue></stringValue>` compiled to `Draft` and activated.

More generally, **clear a field in a Flow record update with an empty `<stringValue></stringValue>`,
not `$GlobalConstant.EmptyString`.** The `<elementReference>$GlobalConstant.EmptyString</elementReference>`
form passes the metadata **deploy** clean but **fails activation** with
`field integrity exception: unknown (The assignment that uses the field "X" has an invalid reference in
"$GlobalConstant.EmptyString".)`. The global constant is reported fine on ordinary Text, but the same
rejection has been seen on a Long Text Area, a picklist, and a lookup, so do not read it as a Long Text
Area limit. Which field types accept it has not been mapped.

**To clear a lookup, assign a `String` variable declared with no default.**
`$GlobalConstant.EmptyString` is rejected on a lookup with the same field integrity exception. The
unset-variable form was verified at run time in a sandbox, the field reading null afterwards, which
matters because Flow skips some null assignments, so a version that deploys clean can still leave the
field populated. One before-save
assignment of a `String` variable to `$Record.<Lookup__c>` both sets and clears the lookup (it holds a
record Id when a Get Records found one, and nothing when it did not), so a flow deciding what a lookup
should be needs no separate clearing branch and does no DML. Whether an empty
`<stringValue></stringValue>` also clears a lookup has not been tested, so prove whichever form you use
by reading the record back.

---

## An `InvalidDraft` that cannot be read, deleted, or deployed over: deploy the next version number

**Symptom: every deploy of the flow fails with `insufficient access rights on cross-reference id`, run
after run, and its latest version reads `InvalidDraft`.** Reading that version fails the same way, even
as a System Administrator: a Tooling `GET .../tooling/sobjects/Flow/<301...>`, and even
`SELECT Id, FullName FROM Flow WHERE Id = '<301...>'`, return `INSUFFICIENT_ACCESS: insufficient access
rights on cross-reference id`, and a Tooling delete returns `FIELD_INTEGRITY_EXCEPTION: Unable to load
specified entity <15-character Id>`. `SELECT Id, VersionNumber, Status` still works, and
`MetadataComponentDependency` still lists the version's references with the missing object simply
absent, so neither names the cause.

**Cause: a deploy saved the version while the org lacked a custom object the flow references, and
every later deploy has to delete that version first.** The saving deploy reports success and lands
`InvalidDraft`, like the missing-field route in the `InvalidDraft` section, but this time the stored
version cannot be loaded back. A deploy over an inactive latest version replaces it instead of editing
it: Salesforce's Tooling API reference for the `Flow` object says that updating a flow version deletes
the existing version and creates a new one from it, with a new Id. The org's `SetupAuditTrail` shows
the pair on every such deploy, "Created flow version #N" and then "Deleted flow version #-N", so the
delete is the step that fails.

**Deploying the missing object afterwards does NOT repair the version.** In the measured sandbox it
stayed unreadable and undeletable, and a check-only deploy of the flows still failed. That the missing
**object**, and not a missing field, is what makes a version unreadable is inference from three cases:
missing fields in production and a missing subflow input in a sandbox each left an `InvalidDraft` that
could still be read or overwritten, and this was the first case with a missing object.

**Fix: deploy the next version number, which never touches the broken version.** The Metadata API's
`Flow` reference documents a version suffix on the flow's name (`<Name>-3` is version 3) and says an
unnumbered name means the latest version. So, with N the broken version's number:

```bash
sf project convert source --metadata Flow:<Name> --output-dir <dir>
# rename <dir>/flows/<Name>.flow to <Name>-<N+1>.flow, and the <members> line in <dir>/package.xml to match
sf project deploy start --dry-run --metadata-dir <dir> --target-org <alias>   # expect created=true for <Name>-<N+1>
sf project deploy start --metadata-dir <dir> --target-org <alias>
```

The new version becomes the latest, so every later unnumbered deploy, a pipeline's included, replaces
it as usual. **Prove that with a check-only unnumbered deploy before calling it fixed.** The broken
version stays behind, inactive and unloadable, and matters again only if every newer version is
deleted, so leave those alone. Nothing tried in the measured case removed it: two Tooling deletes, one
of them after the missing object existed.

**A caller that source ships Active needs its subflow active first.** A sandbox deploy honors source
status, so the caller lands active and immediately calls the subflow's **active** version. A subflow
that never had a healthy version in that org has none, so activate the new one first, with a
`FlowDefinition` `activeVersionNumber` deploy run by an administrator (a deploy-only CI account usually
cannot activate a system-context flow), then deploy the caller on its own and check that it landed
`Active` and not `InvalidDraft`.

**Evidence, from one developer sandbox in 2026.** A pipeline deploy saved versions of two flows while
the org lacked a custom object they referenced, because an earlier deploy of that object had failed for
an unrelated reason. Eight pipeline runs over 24 days then failed on them. One deploy created the next
version of each flow, a second activated the subflow's new version, a third deployed the subflow's
caller on its own, and a check-only unnumbered deploy of both repaired flows then passed.

**The error string alone does not identify this case.** The *Deleting a flow* section records the same
`insufficient access rights on cross-reference id` from a Metadata API destructive delete of a healthy
flow. What identifies this one is a latest version that cannot be read.

---

## The retrieve-returns-latest trap defeats every source-versus-org comparison tool

Because a retrieve returns the **latest** version, **any tool that compares a retrieve against source
is comparing the wrong version whenever the org's active version is not its latest.** A
drift-detection script is exactly such a tool, and it misfiles the case in the reassuring direction:
the flow reads as "diverged, the org's own content, not actionable", when the truth is that the org is
running a version predating a merged change.

Live case, in a shared QA sandbox: a notification flow was Active at **v6**, which read a retired
custom-metadata field and did not reference its replacement at all. **v7 carried the repoint and was
Obsolete.** A retrieve returned v7, so a source-versus-org diff reported the flow as carrying the
repoint. Reading v6 directly settles it, with the single-version REST call from the queries section,
then grep the field names.

**And v6 was active because a person put it back**, so it was not drift to fix. The audit trail showed
a colleague deploying v7, activating it, then reactivating v6 and deactivating v7 two hours later.
Activating v7 to "fix" the divergence would have reversed that.

**Correction: that reactivation was not a judgment about this flow.** Reconstructed later, it covered
every one of the 32 flows the same deploy had touched, so it was a blanket rollback of the deploy (the
section *The active version can agree with production and disagree with source* has the full event).
The lesson to ask whoever did it before reversing it stands; the reading that they weighed this
particular flow does not. **The state itself has since moved on:** a later version became active, with
v6 and v7 both Obsolete, and source now matches the active content in that sandbox and in
production. The mechanism this section teaches is unchanged.

Since `Section` cannot be filtered on `SetupAuditTrail`, select `CreatedDate, CreatedBy.Username,
Action, Section, Display` over a time window and grep the `Display` text. Two traps when reading it:

- **`SetupAuditTrail` does record flow activation performed by a metadata deploy, so a row there is
  not evidence of a Setup UI click.** It misses many components a deploy creates, which makes this easy
  to get backwards, but it logs flow activations and each flow version a deploy creates or deletes.
  Pace is the tell: one bulk activation pass wrote 40-plus rows in under three minutes, which is
  machine-paced rather than hand-clicked.
- **`DeployRequest` retention is not continuous.** In one production org its history skipped a gap of
  more than two months, so a deploy Id recorded at the time could no longer be re-verified. Note what a
  deploy did when it happens, because you might not be able to look it up later.

**It also blocks field deletion, twice over.** Deleting a field needs every referencing flow version
gone, obsolete ones included, and **`MetadataComponentDependency` reports zero dependents because it
only sees current versions**. So a dependency query returning nothing is NOT evidence a field is safe
to delete. The destructive validate is what names the blocking versions, and its error text is
truncated by Salesforce mid-sentence, so it under-reports how many there are.

---

## The active version can agree with production and disagree with source: diff three ways

When an org's active flow version is older than its latest, two readings arrive together and both are
usually wrong: that the org has drifted, and that the difference is "source minus whatever fix never
landed". Measured across a shared QA sandbox and production in 2026, starting from one flow and ending
at 17.

**The event.** One deploy to the shared QA sandbox carried a feature build plus about 32 flow
versions, and about two hours later every one of the 32 was reactivated to its prior version within
two minutes: a blanket rollback, not 32 decisions. The deployed tree was also **behind** the trunk's
head (one reverted flow predated a commit merged three hours earlier), so "latest equals trunk" was
false for that deploy. Three weeks later, 17 of the 32 still had an active version older than their
latest.

**What the 17 turned out to be, once each was fetched three ways (production active, sandbox active,
sandbox latest) and diffed with `status` removed:**

| Verdict | Flows |
|---|---|
| Byte-identical to the reverted copy: a redeploy of unchanged content still creates a version | 12 |
| Reverted copy was OLDER than the active one; the org runs the newer content | 1 |
| Source STALE against both orgs; entry criteria intact; nothing to do in the org | 1 |
| A merged entry-criteria change missing from production AND the sandbox | 3 |

All 17 had the sandbox's active version identical to production's, so none of them was the sandbox
drifting on its own, and only three needed any org action. **Because a redeploy of unchanged content
still creates a version, "active is older than latest" says nothing about whether the content
differs.**

**Source can be stale against BOTH orgs, and a fix committed on top of a stale copy inherits the
staleness.** In one flow, production and the sandbox (byte-identical to each other) populated two
target fields from different source fields than the repository's copy did. A later entry-criteria fix
had been written against the repository's copy, so its `ISCHANGED` list named two fields the orgs do
not propagate and omitted one they do. Deploying source as-is regresses the mapping, which is what the
blanket deploy had done to the sandbox before the rollback undid it. Why source was stale is inference:
the repository's baseline appears to have been captured from an org still on the older build, and a
later additive reconcile against production added missing files without overwriting existing ones. A
second flow had the same shape.

**How to apply.** Before "fixing" a flow whose active version is not its latest, fetch production's
active version, the sandbox's active version, and the sandbox's latest through the Tooling REST
endpoint (one version Id per call, as in the queries section), strip `Metadata.status`, and diff all
three. Identical means nothing to do. When the orgs agree with each other against source, check the
**direction** before naming a side stale: does the org build reference something source lacks (source
is stale), or does source add something the orgs lack (the orgs are behind)? Only then decide whether
the deploy is a capture-then-fix or a plain deploy-and-activate.

**A drift checker that compares a retrieve against the trunk under-counts this.** Its report for the
sandbox listed three flows, each compared against a version the org was not running; the Tooling
`Flow` object grouped by `Definition.DeveloperName` gave 17. It also cannot see a stale source at all,
since its premise is that the trunk is the newer side.

---

## Deleting a flow

**Check EVERY org first, because "inactive in production" is not "dead".** Verified the hard way: a
tech-debt plan listed three flows as retirement candidates on the strength of a production-only check,
and one of them turned out **active in three other orgs** while inactive in production. Deleting it
would have removed working automation from all three. That flow has since been switched off in every
org on purpose, so the example has moved on while the rule stands; the section *Deactivation: a Draft
deploy is not an off-switch* records how long two of those orgs kept running it. The other two
candidates were inactive in every org and were deleted, and one of those was still wanted.

**Inactive in EVERY org is still not dead: a flow shipped Draft on purpose can be waiting for its
go-live date.** In the recorded case a team asked for a notification flow, and it merged as Draft to
go live on a date they would choose. A bulk activation pass turned it on the day before that date and
it was turned off again the same day, nobody activated it on the chosen date, and it sat inactive
until a cleanup deleted it as dead. It was restored nearly two months later, when someone asked
whether it was ready to activate, and removed again the same day, because the requester by then wanted
something different. **So before deleting an inactive flow, read the commit that added it**
(`git log --diff-filter=A --format='%h %ad%n%B' -- <path>`), and if it says the flow ships Draft to be
activated later, ask its requester or author whether it is still wanted. Ask again before restoring
one, since a request that has waited months might no longer be what they want.

This is the mirror of the source-status section: source status lies in one direction, a single org's
status lies in the other. One query per org settles it, then enumerate versions per org with the
Tooling `Flow` object before deleting anything. Also check whether an open PR touches the flow, which
on its own disqualifies it as a clean deletion.

**Delete the `Flow` versions via the Tooling API, not via MDAPI `destructiveChanges.xml`.** A
destructive deploy naming the flow fails check-only with **`insufficient access rights on cross-reference
id`**. Nothing in that message points at flows, versions, or what the cross-reference is, and in the
measured case the flow was neither active, managed, a template, nor holding any `FlowInterview`. **Do
not chase permissions or references on it.** The same message on every ordinary deploy of a flow is a
different case: see the section *An `InvalidDraft` that cannot be read, deleted, or deployed over*.

```bash
sf data delete record --use-tooling-api --sobject Flow --record-id <301...>
```

**Deleting the last version removes the `FlowDefinition` automatically.** Confirmed at scale: after
removing nine versions across five orgs, a `FlowDefinition` query returned zero rows in every org. There
is no orphan cleanup step.

Recipe: query the versions, deactivate first if any is Active (remembering that a `status=Draft` deploy
is not deactivation), then Tooling-delete each version.

**On the pre-delete safety check:** `MetadataComponentDependency` **does** carry
`MetadataComponentName` and `RefMetadataComponentName`, and selecting both works. What they are not is
**filterable**. So filter on `RefMetadataComponentId`, using the `301…` version Ids, and select the
names for readability. Remember the limitation above: it sees current versions only.

**An OBSOLETE orchestration version blocks deleting a subflow it once called, and every "nothing
references this" check is blind to it.** Salesforce refuses with *"Cannot complete this operation.
This flow definition is referenced elsewhere in Salesforce. Remove the usage and try again. :
Orchestration Step"*. Measured in one production org: an orchestration's v1 and v2 still referenced
four retired subflows, while v3 through the active v5 referenced only their replacements. So
`MetadataComponentDependency` (no dependents), the active version's metadata, and an Apex sweep were
all correct, and all described current versions only. **A clean dependency result licenses a
deactivation and says nothing about a deletion**, the same shape as the field-deletion rule in the
retrieve-returns-latest section. Retiring the obsolete orchestration versions first is the route, and
it carries risk, because a running orchestration continues on the version it started on. So before
deactivating a subflow an orchestration uses, list the open `FlowOrchestrationInstance` rows
(`Status`, `CreatedDate`, `TriggeringRecord`, `OrchestrationDeveloperName`) and compare each
`CreatedDate` with each version's `CreatedDate` from Tooling `Flow`, since `FlowDefinitionVersionName`
is null on every row (see the section on a running orchestration).

**An orchestration is itself record-triggered, so count flows by `processType`, not by `triggerType`
alone.** In one source tree, two of the flows a `triggerType` filter counted as record-triggered were
`ApprovalWorkflow` orchestrations: the approval engine itself, and not candidates for retirement or
consolidation.

**A sandbox-sync tool listing flows to delete is reporting the source-side delta, not the org side.**
In one case three flows were listed and only one existed in the sandbox; the others had never been
deployed there. Confirm each exists before reporting it deleted.

---

## Apex `Flow.Interview` can run a later Draft, not the active version, and drop its input silently

Measured while diagnosing five failing tests. The flow held **v2 Active**, carrying the input variable
the test passed, and **v3 Draft**, an older design without that variable.
`Flow.Interview.createInterview('<Name>', {recordVar => rec}).start()` ran **v3**, confirmed from the
debug log's `FLOW_CREATE_INTERVIEW_BEGIN` naming v3's Id while `FlowDefinitionView.ActiveVersionId`
named v2.

**The failure mode is silence.** v3 had no `recordVar`, so the input went nowhere: no exception, no
`FLOW_VALUE_ASSIGNMENT` line at all, the criteria check read a null field, took the default connector,
and ended. Zero DML, zero errors. **A `try/catch` around the interview counts no failure**, so batch
code that tallies exceptions reports a clean run while doing nothing.

**How the shadowing Draft got there, and this is the reusable part:** the trunk still carried the older
version of the flow, and a routine "sync my sandbox from the trunk" deployed it **on top of** the
branch's v2, landing as a later Draft. So **syncing a sandbox can shadow an unmerged branch's active
flow**, and every Apex test driving that flow starts failing for a reason that is nowhere in the branch.
The same branch validated with zero failures in a CI org that had no shadowing Draft.

**Why Apex chose the Draft is NOT established.** The `Flow.Interview` documentation states no
version-selection rule. The running user did hold **Manage Flow**
(`PermissionsManageInteraction`), which is the usual explanation offered for latest-over-active, but
that link was not verified. Treat it as an untested hypothesis.

**How to apply:** when an Apex test that launches a flow fails with everything reading null, or a
criteria check is inexplicably false, enumerate the flow's versions before touching the Apex and
compare the Id in `FLOW_CREATE_INTERVIEW_BEGIN` against `FlowDefinitionView.ActiveVersionId`. Flow
events need a DebugLevel with `Workflow=FINEST`; the org default omits them entirely, so the first log
looks as though the flow never ran.

---

## A running orchestration keeps the stage structure of the version it started on

Verified on six `FlowOrchestrationInstance` rows with `Status = InProgress`, sitting in stages that a
redesign had deleted months earlier. **Deploying and activating a new orchestration version does not
change anything already in flight.**

**The QA consequence is a mixed state that reads as a new defect.** A record-triggered before-save flow
is version-independent and applies to every new record immediately, while an orchestration change
reaches only rounds started afterwards. A tester's parked records will therefore show the fixed
behavior from one half alongside the old behavior from the other.

**Tell a tester to start a fresh submission after an orchestration fix, and do not let them resume a
parked record.**

`FlowOrchestrationInstance.FlowDefinitionVersionName` is null on every row, so it cannot tell you which
version an instance is on. `CurrentStage` against the current design is the usable signal.

---

## Two deploy-time gotchas worth knowing

**`emailSimple`**, the core Send Email action, requires
`<flowTransactionModel>CurrentTransaction</flowTransactionModel>`. `Automatic` fails the deploy with
*"The action 'EMAILSIMPLE' only supports 'CurrentTransaction' in 'FlowTransactionModel'"*.

**A record-triggered flow's entry-criteria FORMULA cannot reference a polymorphic reference field.**
`ISCHANGED({!$Record.AssignedToId})` on an object whose `AssignedToId` points to Group **or** User fails
check-only deploy with the misleading *"Field AssignedToId does not exist. Check spelling."* Use a
**structured** entry condition (`<filters>` with `IsNull` / `EqualTo`), which accepts the polymorphic
field. The consequence is that "run only when the assignee changes" is **not expressible** for a
polymorphic assignee; the closest is "assignee is set". Applies to `OwnerId`, `WhoId`, `WhatId`,
`RelatedRecordId`, and `AssignedToId`.
