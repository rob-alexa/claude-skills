---
name: salesforce-metadata-deploy
description: "Reading a Salesforce metadata deploy result, and the deploys that succeed while landing nothing or while removing something from the org. TRIGGER when: reading a deploy result or its componentSuccesses, deploying a permission set, permission set group, or profile, redeploying an LWC or Aura bundle, 'This schedulable class has jobs pending or in progress', a field delete blocked by a Lightning page, or a change that deployed green is missing from the org. Not for picklist values (salesforce-picklist-changes)."
metadata:
  version: "1.0"
  license: MIT
---

# salesforce-metadata-deploy

How to read a metadata deploy's verdict, and the deploys that report success while landing nothing
or while removing something the org held. Several component types replace the org's copy instead of
merging into it, so what a deploy takes away depends on what the org held, and the deploy result
never shows you that.

Point-in-time: measured on Salesforce orgs during 2026. Verify against your own org before asserting
any of it as current fact.

---

## Read the verdict in order: `status`, then the components, then the org

1. **`status` first.** `componentSuccesses` means something only once `status` is `Succeeded`. A
   failed deploy rolls back whole and still lists its constructive components as successes with
   `changed=true`. Measured: a deploy bundling constructive and destructive changes reported
   `status: Failed`, `3/4` components, and `errors: 1`, listed all three constructive components
   under `componentSuccesses`, and landed none of them, which a describe against the org confirmed
   right afterward.
2. **Then the per-component result.** Confirm that the specific field, permission, or flow you were
   deploying appears in `componentSuccesses`. In the case behind this rule, a field never deployed,
   nothing in the overall result said so, and a tester found it afterward.
3. **Then the org.** A describe or a query against the org is what settles it; neither of the first
   two steps can. If a UI check right after the deploy still shows the old field, that is a cached
   describe in the browser session, covered in `salesforce-flow-and-ui-defects`.

Reading the JSON from `sf project deploy start --json` (or `sf project deploy validate --json`):

```bash
sf project deploy start --source-dir <path> --json > deploy.json
jq -r '.result.status // "NO RESULT: \(.message)"' deploy.json
jq -r '[.result.details.componentSuccesses // empty] | flatten | .[]
  | select((.componentType // "") != "")
  | "\(.componentType) \(.fullName) changed=\(.changed) deleted=\(.deleted)"' deploy.json
jq -r '[.result.details.componentFailures // empty] | flatten | .[]
  | "\(.componentType) \(.fullName): \(.problem)"' deploy.json
jq -r '.result.details.runTestResult.failures[]?
  | "\(.name).\(.methodName): \(.message)"' deploy.json
jq -r '.result.numberComponentsDeployed' deploy.json
```

Four traps in that JSON, each met in practice:

- **`componentSuccesses` carries a `package.xml` entry with an empty `componentType`**, which is
  what the `select` drops. It is not a component, so do not count it as one.
- **Apex test failures populate neither `componentFailures` nor the top-level `.message`.** They are
  only in `.result.details.runTestResult.failures`, so a failed validate can otherwise show no
  stated cause at all.
- **A failed `sf project deploy validate` has come back with no `.result` at all**: the deploy Id is
  at `.data.deployId` and the reason is the top-level `.message`. A `--dry-run` failure keeps the
  normal `.result`. Reading `.result.status` alone then prints `null`, which looks like nothing to
  report.
- **A quick deploy replays a validated payload and does not always itemize `componentSuccesses`**,
  so cross-check `numberComponentsDeployed` before reading an empty list as "nothing deployed". If
  both are zero on a payload that was not empty, the deploy touched nothing, whatever its status
  says.

---

## A permission set deploy replaces the set; a profile deploy merges

- **A permission set is replaced wholesale by whatever the file holds.** Measured: a permission set
  file carrying only one new object's permissions cut the set in the org from 70 object and 2,288
  field permissions to 2 and 116. The System Administrator profile in the same deploy merged fine,
  which is what confirmed the asymmetry.
- **A profile merges.** Only the entries present in the file are updated, and the rest of the
  profile is left as it was.
- **Every element type in the file is part of the replacement, tab settings included.** A
  permission set that made a tab visible in the org was deployed from a file with no tab settings,
  the deploy set the tab to hidden, and the 243 active users whose only path to that tab was that
  permission set lost it. Nothing in the deploy result pointed at it.
- **A delta deploy is per file, so a one-line change ships the whole file.** A change removing 40
  lines of retired references from one permission set would have stripped 70 unrelated entries (11
  field and 59 object permissions) that the org held and the file lacked. Nothing in the change
  pointed at them.

**So deploy the complete file, retrieved fresh, never an incomplete slice:**

- **Retrieve into a separate `--output-dir`**, a scratch path inside the project, since the CLI
  rejects one outside it. A plain retrieve into the project merges with your local copy and hands
  back the local shape: measured, it returned exactly the 65 local entries, reordered, which reads
  as "in sync" whatever the org holds.
- **A retrieve can itself come back short of the org.** One lacked grants on seven fields that the
  org held and the metadata could carry, so deploying it would have stripped them. Before deploying
  a whole file, compare the retrieve's `fieldPermissions` with the org's `FieldPermissions` rows by
  field name, and look into each field the retrieve lacks. Do not compare counts: SOQL returns rows
  the metadata never carries (a gap of about 120 was normal on one large set), so a count comparison
  reports drift where there is none.
- **For one new grant, insert one `FieldPermissions` row instead of deploying the file**, then read
  it back and check that the set's total moved by exactly one. A permission set group's own
  aggregate set refuses the insert with `INVALID_CROSS_REFERENCE_KEY`, so insert on a member set and
  let the group re-aggregate. Until the group's `Status` reads `Updated`, a check through the group
  still shows the old access.

---

## A permission set group's member list is replaced the same way

Deploying a permission set group's file sets its members to exactly the file's `<permissionSets>`
list. Any member the org's group holds and the file lacks is removed, and every user holding the
group loses that member's access unless they hold it some other way.

**Removing a member writes no per-user audit row.** `SetupAuditTrail` logs only the membership
change itself, as `PermissionSetGroupComponentRemoved`, so afterward nothing tells you who lost
what. Measured: a 14-day search over 3,273 audit rows named neither of the two users who reported
losing access.

So do the accounting before the deploy, since nothing records it after:

```bash
# Members the org's group holds now; compare with the file's <permissionSets> entries
sf data query --query "SELECT PermissionSet.Name FROM PermissionSetGroupComponent
  WHERE PermissionSetGroup.DeveloperName = '<Group>'"
# Active users who hold the group, and so lose whatever member the deploy removes
sf data query --query "SELECT Assignee.Username FROM PermissionSetAssignment
  WHERE PermissionSetGroup.DeveloperName = '<Group>' AND Assignee.IsActive = true"
```

To add one member without deploying the membership file, insert a `PermissionSetGroupComponent` row,
which leaves the rest of the group alone. That route was used in a sandbox in 2026.

---

## An LWC or Aura bundle deploy deletes the files it does not carry

**A bundle deploys as a unit, so any file the org's copy holds and your deploy lacks is deleted**,
and the result reports the bundle `changed=true deleted=false`. Nothing in it shows the loss.
Measured in a sandbox in 2026: an LWC redeployed with three of its five files kept three, and an
Aura bundle sent without its helper and style went from four definitions to two.

This bites when the org's bundle gained a file your copy never had, from someone else's change or an
edit made in the org, or when your copy came from an incomplete retrieve. Compare the org's files
with your bundle directory before deploying:

```bash
sf data query --use-tooling-api --query "SELECT FilePath FROM LightningComponentResource
  WHERE LightningComponentBundle.DeveloperName = '<name>'"
sf data query --use-tooling-api --query "SELECT DefType FROM AuraDefinition
  WHERE AuraDefinitionBundle.DeveloperName = '<name>'"
```

---

## A class a scheduled job uses blocks the deploy, unless the org allows it

**A deploy that changes an Apex class a scheduled job runs or references fails and rolls back
whole** with:

```
This schedulable class has jobs pending or in progress
```

Only the blocking class lists its `CronTrigger` Ids. Every other class in the payload repeats the
error with an empty `CronTrigger IDs ()`, so the result reads as if all of them were scheduled. Find
the entry that carries Ids and resolve them:

```bash
sf data query --query "SELECT Id, CronJobDetail.Name, State, NextFireTime FROM CronTrigger
  WHERE Id IN ('<id>')"
```

A second entry per class names the fix: the Deployment Settings option **Allow deployments of
components when corresponding Apex jobs are pending or in progress**, which is
`doesSkipAsyncApexValidation` in `Settings:Deployment`. Seen in 2026, after which the setting was
turned on in a sandbox and in production so the class could change while its jobs stayed scheduled.

- **Turn the setting on instead of unscheduling the jobs around each deploy.** Unscheduling clears
  one deploy, and then has to be repeated, with every job rescheduled correctly, for each later
  change to those classes.
- **It is set per org.** An org where nobody has turned it on fails this way, so a sandbox where
  someone scheduled the job can refuse a deploy that production accepts, and the reverse.
- **Once it is on, leave it on.** Switching it off as tidy-up brings the failure back for every
  later change to those classes.
- **To set it from source**, retrieve `Settings:Deployment` fresh, change that one value, deploy
  only that file, and read it back. Production refuses `--test-level NoTestRun`; the default level
  runs no tests on a deploy that carries no Apex. Setup's Deployment Settings page sets the same
  value.
- **The cost, per the Setup page's own warning:** a deploy that lands while one of those jobs is
  running can make that run fail, so know when your scheduled jobs run.

---

## A Lightning page placement blocks deleting a field, and the dependency query misses it

Deleting a field that sits on a Lightning record page (a FlexiPage) fails the destructive deploy,
one error per placement:

```
The <Field Label> custom field is used in a component on the <Page Label> Lightning page. : Lightning Page.
```

Measured once in a sandbox: three placements, three errors, while `MetadataComponentDependency` for
the field's Id listed only a page layout and none of the three pages. A second shape, measured
separately: a field shown as a column in a dynamic related list blocks the delete from the page that
hosts the list, normally another object's record page, so the page to edit is not always on the
field's own object:

```
Referenced by the relatedListFieldAliases property of the lst:dynamicRelatedList component in this Lightning page.
```

In that case the page layout, compact layout, and permission sets that also referenced the field did
not block the delete. Salesforce removes a deleted field from page layouts on its own; it does not
edit Lightning pages.

The order that works:

1. **Run the destructive deploy check-only (`--dry-run`) first.** It names the blocking placements.
2. **Remove the field from each page it names**, the component and any dynamic related list column.
   Start from the org's own freshly retrieved copy of each page, not your source copy, if the page
   might have been edited in the org: deploying a page sends the whole page.
3. **Deploy the pages.**
4. **Run the destructive deploy.** Once the field is gone from source, pass a `--manifest` whose
   `package.xml` holds only a `<version>` element, with the field named in
   `--post-destructive-changes`. Passing the destructive file as the manifest as well fails with
   *"An object '<Object>.<Field>' of type CustomField was named in package.xml, but was not found in
   zipped directory"*.

Flow versions that reference the field block the delete as well, obsolete ones included; that
sequence is in `salesforce-flow-versions`.

---

## Covered by other skills

- **Deleting a field or a flow that flow versions reference**, and why a dependency query returning
  nothing does not mean it is safe: `salesforce-flow-versions`.
- **A UI check right after a deploy showing the old field**, or a colleague reporting a newly
  deployed field as missing: `salesforce-flow-and-ui-defects`.
- **Picklist values**, including what a picklist deploy does to the values the file leaves out:
  `salesforce-picklist-changes`.
