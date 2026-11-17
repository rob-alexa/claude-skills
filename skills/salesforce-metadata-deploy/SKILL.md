---
name: salesforce-metadata-deploy
description: "Reading a Salesforce metadata deploy result, and the deploys that succeed while landing nothing or while removing something from the org. TRIGGER when: reading a deploy result or its componentSuccesses, deploying a permission set, permission set group, profile, or External Client App, redeploying an LWC or Aura bundle, 'This schedulable class has jobs pending or in progress' or 'is duplicated at this location', deleting or restoring a field, converting a Text Area to a Long Text Area, or a change that deployed green is missing from the org. Not for picklist values (salesforce-picklist-changes)."
metadata:
  version: "1.1"
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

**A failed deploy has once been seen leaving permission set entries stripped.** A sandbox took two
failed deploys, each bundling a constructive change with a field delete and each rolled back whole,
and afterward one permission set had lost its entire section for the object being changed: the
object permission and both field permissions. A second sandbox took the identical constructive
payload with no failed deploy and kept all three, and the components themselves rolled back
correctly in both. It was seen once and never reproduced, so it is an observation, not an
established mechanism. Check for it after a failed deploy anyway, because the symptom points
somewhere else: a field with no field-level security is missing from `sf sobject describe` and fails
Apex compilation with *"No such column"*, while `sf org list metadata --metadata-type CustomField`
still lists it, so it reads as a failed or half-finished delete instead of lost access. Read the
grants before redeploying anything:

```bash
sf data query --query "SELECT Field, Parent.Name, PermissionsRead, PermissionsEdit
  FROM FieldPermissions WHERE SobjectType = '<Object__c>'"
```

The repair used was redeploying the permission set from source control. That replaces the whole set,
so first check what the org holds that the file lacks (the permission set section), or insert the
lost rows one at a time instead. If users reach the set through a permission set group, the restored
grant does not apply until the group's `Status` reads `Updated`, and a describe run before then
still cannot see the field, which looks exactly like the repair having failed.

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

**Two ways a complete file fails to deploy.** Both fail loudly and land nothing:

- **A stale file fails on the first reference the target org lacks.** A full file taken from another
  org, or an old retrieve, can name fields, objects, or record types the target does not have, and
  the deploy fails whole on the first one. It reports only that first one, so fixing it exposes the
  next, which reads as a new regression; find every bad reference before deploying again. Settle
  whether a field exists with `sf org list metadata --metadata-type CustomField`, not with
  `sf sobject describe` or a `FieldDefinition` query: both hide a real field you hold no field-level
  security on, so they report it as absent, and stripping it on their word removes a real grant. For
  objects, an `EntityDefinition` query has come back empty for objects that exist, so trust the
  describe there.
- **Each element type has to be one contiguous run**: every `fieldPermissions` entry together, every
  `objectPermissions` entry together, and so on. An entry outside its type's run fails the deploy
  with *"element X is duplicated at this location"*. When adding entries by hand, append each after
  the last existing block of its type instead of re-sorting the region: measured, that kept a
  70-entry repair to a 645-line addition, where re-sorting would have reshuffled 14,000 lines. A
  check-only deploy of the result reports the permission set `changed=false` when the file matches
  the org exactly.

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

**A holder count overstates the loss when the removed member is a package permission set that works
only when assigned directly.** A managed package can gate a feature on the user's own
`PermissionSetAssignment` row for its permission set. An assignment that arrives through a group
names the group's own aggregate permission set, never its members, so group membership never
satisfied that gate, and the users who rely on it hold the set directly. Measured: a sandbox's group
held three package permission sets that the file lacked, the holder count said up to 75 active users
would lose access, and all three turned out redundant, because everyone who needed them held them
directly. So before a large count argues against a correct deploy, count the direct assignments,
which a query on the member's own name returns alone:

```bash
sf data query --query "SELECT Assignee.Username FROM PermissionSetAssignment
  WHERE PermissionSet.Name = '<PackagePermissionSet>' AND Assignee.IsActive = true"
```

The same gate cuts the other way: never remove such a direct assignment, or fold it into a group, on
the grounds that a group already grants the same access. Every permission check still passes while
the feature stops working. In the cases seen, a packaged component refused with *"you may not have
permission to view this page"* while object access, field-level security, and the license were all
in place, and the managed debug log showed only a `COUNT()` on `PermissionSetAssignment` returning
no rows.

**A member that is a managed package's permission set fails every org without that package.** A
group's member list is checked against the target org, so where the package is not installed the
group fails with:

```
Cannot create Permission Set Group Components since the following permission set names are invalid: <name>
```

A deploy is atomic, so that one member rolls back the rest of the payload with it. Measured: a
package installed in production, with its permission set tracked as a member of a group in source,
failed the first sync into a sandbox that lacked the package. Install the package in every org the
group deploys to. Dropping the member from your file instead is the wrong fix: the next deploy of
the group to production removes it there.

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

## Deleting a field: which layouts can name it, and how long it stays restorable

**A layout last modified before a field was created cannot reference it.** That makes a cheap proof
when you need to know whether any page layout names a field you are deleting.
`sf org list metadata --metadata-type Layout` returns every layout with its `lastModifiedDate`, and
the field's `CreatedDate` is on its Tooling `CustomField` row (`FieldDefinition` carries none). One
listing settled the question for a production delete in 2026.

```bash
sf org list metadata --metadata-type Layout --json \
  | jq -r '.result[] | "\(.lastModifiedDate)  \(.fullName)"' | sort
sf data query --use-tooling-api --query "SELECT DeveloperName, CreatedDate FROM CustomField
  WHERE Id = '<00N...>'"
```

It proves one direction only. A layout modified after the field was created might or might not name
it, so retrieve those and look. And a managed package's components can carry the package's install
stamp instead of any edit date (measured on Lightning components, where hundreds from one package
shared one `LastModifiedDate`), so on a managed layout look at how the dates spread across the
package before reading anything into one of them.

**A deleted custom field stays restorable, with its data, for about 15 days**, from the Deleted
Fields page on its object in Setup. Say so when proposing a delete, since it lowers the stakes of
the decision. The field's Tooling `CustomField` row stays behind, its `DeveloperName` given a `_del`
suffix (seen in a sandbox: `My_Field__c` shows as `My_Field_del`), with no `IsDeleted` flag and a
`ManageableState` reading `unmanaged` exactly as a live field's does. The row outlives the restore
window, since one count found rows for fields deleted 26 days earlier, so it is not by itself
evidence that a field can still be restored. It also inflates a field inventory: that count returned
18 fields on an object that held 10, so exclude `_del` names, then settle the number with
`sf sobject describe`.

---

## Widening a Text Area to a Long Text Area deploys green and breaks filters

A Text Area (fixed at 255 characters, with no `<length>`) is filterable, sortable, and groupable. A
Long Text Area is none of the three, in SOQL, reports, and list views alike. The conversion deploys
green and keeps every value (verified byte for byte on 24 records), and then a query, report filter,
or list view filter on the field fails:

```
INVALID_FIELD: field '<field>' can not be filtered in a query call
```

Salesforce does refuse the conversion while a formula or validation rule depends on the field, so
those are safe. Report and list view filters are the exposure, and `MetadataComponentDependency`
will not answer a `RefMetadataComponentName` query, so there is no quick way to list them. Check by
hand before converting, and afterward read the describe, where `filterable` turns `false`, instead
of assuming a green deploy changed nothing.

Widening is otherwise safe, and it is the only fix when source data runs past 255 characters,
because Salesforce rejects the whole record with `STRING_TOO_LONG` instead of truncating the field.
A `Url` field cannot be widened at all, and Lightning inline edit truncates an over-long paste
instead of erroring; both are in `salesforce-flow-and-ui-defects`.

---

## An External Client App's first deploy to an org takes two passes

**An `OauthTokenExchangeHandler` does not resolve an `ExternalClientApplication` in its own deploy
payload**, so the app has to exist in the target org first. Measured: a delta of seven components in
which six validated and the handler alone failed with:

```
In field: ExternalClientApplication - no ExternalClientApplication named <App_Name> found
```

So deploy the External Client App and its Apex first, and the handler once they are in the org. A
pipeline that validates each pull request's delta against an org cannot land both in one pull
request: merge the app first, let it reach the org, and the handler then validates on its own. It is
a one-time bootstrap per org, not a defect in either file.

**Two fields are org-scoped and do not belong in source:**

- **`ExtlClntAppOauthSettings.oauthLink`** points at a record instance (`<orgId>:<recordId>`), so it
  resolves in no other org, and the failure misleads:

  ```
  We couldn't update your OAuth link, because either your external client app or the external client app that you are trying to associate with doesn't have the distribution state PACKAGED
  ```

  It reads as a distribution-state problem and is not one. Drop the element from source.
- **`OauthTokenExchangeHandler.apexExecutionUser`** holds a username, which a sandbox refresh
  suffixes, so no single value resolves in more than one org and there is nothing to fix in the
  file. The handler was kept in source as documentation and listed in `.forceignore`, so no deploy
  carries it.

`orgScopedExternalApp` is tolerated: apps carrying one sandbox's org Id still validated against a
different org.

---

## Covered by other skills

- **Deleting a field or a flow that flow versions reference**, and why a dependency query returning
  nothing does not mean it is safe: `salesforce-flow-versions`.
- **A UI check right after a deploy showing the old field**, or a colleague reporting a newly
  deployed field as missing: `salesforce-flow-and-ui-defects`.
- **Picklist values**, including what a picklist deploy does to the values the file leaves out:
  `salesforce-picklist-changes`.
- **A field's `unique` setting**, which deploys green and decides whether a load can write one value
  to many records: `salesforce-data-loading`.
