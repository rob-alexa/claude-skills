---
name: salesforce-picklist-changes
description: "Changing a Salesforce picklist's values: whether you may, and what a deploy does to the values your file leaves out. TRIGGER when: adding, removing, renaming, deactivating, or reordering a picklist value, deploying a picklist field or value set, a value missing from a retrieve or a diff, a managed-package picklist, a describe reporting `restrictedPicklist`, RESTRICTED_PICKLIST or 'bad value for restricted picklist field', 'Cannot modify managed object' naming Description, a dependent picklist or `validFor`, moving a picklist onto a global value set, or comparing a picklist between two orgs. Not for creating a new picklist field."
metadata:
  version: "1.0"
  license: MIT
---

# salesforce-picklist-changes

Whether you may change a picklist's values, what a deploy does to the values your file leaves out,
and how to compare two value sets without the comparison misleading you. The failures it prevents
are a green deploy that switches values off in production, and a recommendation about who may edit a
value set that rests on evidence that cannot answer the question.

**The shape most of these share: the platform's answer to "may I change this?" is yes, and it is the
wrong question to have asked.** A describe reports `restrictedPicklist` and a namespace, a
check-only deploy comes back green, and neither is permission. On a packaged field the only guard is
text the vendor wrote in the field's description, and a describe does not return it.

Reading a deploy's verdict in general is `salesforce-metadata-deploy`; this skill is the home for
what a deploy does to a picklist. A picklist default that reaches no existing record is in
`salesforce-flow-and-ui-defects`.

Point-in-time: measured on Salesforce orgs during 2026. Verify against your own org before asserting
any of it as current fact.

The `jq` filters here read `.result.records[]` without a `?` on purpose. A failed `sf ... --json`
command still prints its error as JSON on standard output, and `[]?` turns that into an empty result
that exits 0, which reads as "no records" rather than as a failure.

---

## Check these in order, and the first is the one that gets skipped

1. **Read the field's description.** On a packaged field it is the only guard there is, and a
   describe cannot give it to you. See *A package can mark a protected field only in its
   description*.
2. **Set `restricted` aside.** It answers a different question. See *What `restricted` actually
   enforces*.
3. **Work out what your file would switch off.** A deploy replaces the value set, so diff the active
   values in your file against every org it will reach, decoding XML entities first. On an
   unrestricted field, read the inactive values from Setup, because a retrieve leaves them out.
4. **Then decide** whether to extend the existing set or add a field of your own.

---

## A picklist deploy replaces the value set, in both directions

**Deploying a picklist field makes the org's active values match the file.** Values in the file and
not the org are added; values in the org and not the file are deactivated, with no Setup step, no
warning, and no component failure. Managed (packaged) fields behave the same way.

Measured, not inferred: a sandbox held a managed picklist's 26 active values. Deploying a 19-value
file took it to 19, adding five and deactivating all 12 the file lacked. Redeploying the 26-value
file reactivated those 12 and took the five back out, returning the active set to the baseline
exactly.

What follows from it:

- **Do not reason from "it is a managed picklist, so a subscriber deploy must be additive."** It is
  not. That theory was formed and disproved on the way to the measurement.
- **A reduced file is a deactivation, whatever the change was meant to be.** Capturing a sandbox's
  value set into source and deploying it to production switches off every value production has and
  the sandbox lacks, and the deploy reports success. That is why capturing a sandbox's picklist
  drift back into source is dangerous rather than cosmetic.
- **Deactivated is not deleted.** Records holding an omitted value keep it, nothing can select it
  anymore, and anything that keys off it (a validation rule, a flow decision, a report filter)
  still sees it on those records. See *After you remove, deactivate, or rename a value*.
- **Deploy the retrieved file with your change in it**, carrying every existing value, never a file
  that names only the value you are adding. Retrieve it from the org you are deploying to, and diff
  it against every other org it will reach, since they can differ.
- **Deploy a controlling and a dependent picklist together.** See *Dependent picklists*.

**A new value reaches every record type only where no record type restricts the field.** Where a
record type does, add the value to that record type's own picklist assignment as well, or its users
never see it. In the recorded case a field with no record-type block took new values immediately,
while a field one record type restricted to two values needed each new value added to that record
type.

---

## What `restricted` actually enforces

**It is a write-time constraint on data, not a limit on who may change the value set.** Salesforce
describes a restricted picklist as one limited to the values an admin defined, so that users cannot
load redundant or erroneous values through the API
([Picklist Limitations](https://help.salesforce.com/s/articleView?id=platform.picklist_limitations.htm&type=5)).
It is enforced against users and the API at save time, which is where `RESTRICTED_PICKLIST` and
`bad value for restricted picklist field` come from: records failing to save, never a metadata
change being refused.

Three consequences, none of which makes it a permission:

- An admin can switch the flag off, through *Restrict picklist to the values defined in the value
  set*
  ([Add or Edit Picklist Values](https://help.salesforce.com/s/articleView?id=platform.updating_picklists.htm&type=5)),
  so it protects nothing from an admin.
- Global value sets are always restricted, so the flag says nothing field-specific about one.
- What it changes for what you can build is a limit. Per the limitations article, a restricted
  picklist holds 1,000 values counting active and inactive together, while an unrestricted one holds
  1,000 active plus up to 4,000 inactive.

**So do not lead a recommendation with "it is a restricted picklist."** It implies a barrier the
flag does not create, and it displaces the description check that actually decides the case.

### `false` is not permission either

**`restrictedPicklist=false` does not mean the value set is subscriber-editable.** What a subscriber
may edit on a packaged field is settled by the packaging guide, not by this flag, and nothing ties
the two together. They are set by different mechanisms: the restriction is a checkbox any admin can
toggle, and the guard is description text the vendor wrote. So neither can be read off the other, in
either direction. In the recorded checks two pairs happened to line up (a restricted field that
carried the guard, an unrestricted one that did not), which is too small a sample to show that they
travel together.

This direction fails in the reassuring way. Reading `true` as a barrier stops you doing something
legitimate, and someone notices. Reading `false` as permission has you assert a license the describe
never granted, and nothing contradicts you.

**Expect to get this wrong in both directions.** In the project this skill comes from, the
conflation was corrected repeatedly across sessions and written down in four places, every one of
them aimed at reading `true` as a barrier. It then recurred the other way, with the written
correction in front of the session: a field was described as subscriber-editable because
`restricted` was `false`, and a further inference was built on top. That every countermeasure
pointed one way might be why it got through; that is an inference about the cause, not a
measurement. **Run the description query instead of reasoning about the flag.** It is the one step
neither direction of the mistake can fake.

### What `false` does buy you: values the value set does not hold

An unrestricted picklist accepts any string through the API, a data load, or Apex, with no error and
no warning. So records can carry values that are absent from the field's value set and that nobody
can select in the UI.

**A value-set diff cannot see those**, because it compares defined values, and `sf sobject describe`
returns active values only. An orphan that lives purely in the data passes every value-set check
while still appearing in reports, list views, and a `GROUP BY` as a category nobody recognizes. Find
them over the records instead, after checking that the describe reports the field `groupable`:

```bash
sf data query --query "SELECT <FIELD> v, COUNT(Id) n FROM <OBJECT> GROUP BY <FIELD> ORDER BY COUNT(Id) DESC" --json \
  | jq -r '.result.records[] | "\(.n)\t\(.v // "(blank)")"'

sf sobject describe --sobject <OBJECT> --json \
  | jq -r --arg f '<FIELD>' '.result.fields[] | select(.name == $f) | .picklistValues[] | "\(.value)\t\(.active)"'
```

Anything in the first list and not the second is an orphan. Measured in a production org: three
records on a managed, unrestricted picklist carried a value that was not one of the field's seven
active values. Nothing refused the write, and the value has no route back into the picker.

**So `restricted` answers two questions, and neither is the one usually being asked.** It tells you
whether a bad write is refused, and it sets the value limits. It never tells you whether you may
change the value set, and on an unrestricted field it means the data is no longer bounded by the
metadata.

---

## What a subscriber may change on a packaged picklist

**Adding, renaming, editing, and deleting values on a packaged custom picklist is documented,
supported subscriber behavior.** Salesforce's packaging guide states it as a warning to package
developers, that subscribers can rename, add, edit, or delete a custom field's picklist values
([Components Available in Second-Generation Managed Packages](https://developer.salesforce.com/docs/atlas.en-us.packagingGuide.meta/packagingGuide/packaging_component_attributes.htm)).
Its `CustomField` manageability table never lists picklist values among the locked properties. As
read in 2026 (check the current page before citing it):

| Who can edit | `CustomField` properties |
|---|---|
| Neither party | Child Relationship Name, Data Type, External ID, Field Name, the three Roll-Up Summary attributes, Unique |
| Package developer only | Auto-Number Display Format, Decimal Places, Description, Default Value, Field Label, Formula, Length, Lookup Filter, Related List Label, Required, Roll-Up Summary Filter Criteria |
| Both | Chatter Feed Tracking, Help Text, Mask Type, Mask Character, Sharing Setting, Sort Picklist Values, Track Field History |

**So the managed namespace is not the barrier either, and one error will suggest otherwise.**
`Description` is developer-only, so a hand-built payload that omits it fails on the description
before the values are ever reached:

```
Cannot modify managed object: entity=CustomFieldDefinition, component=<id>, field=Description, state=installed
```

**Do not read that as the value set being protected.** Retrieve the field and deploy the retrieved
file with your one value added. A `--dry-run` deploy of exactly that, on a managed field with
`restricted=true`, came back `Succeeded` with `changed=true` and no component errors.

### A package can mark a protected field only in its description

A package that depends on a picklist's exact values has no platform mechanism to lock them. What a
vendor can do, and what at least one does, is say so in the field's description: a note asking
subscribers to leave the field's values as they are because the package relies on them.
**Salesforce enforces none of it.** The green `--dry-run` in *What a subscriber may change
on a packaged picklist* was on a field carrying exactly that note.

Read the description before proposing a value:

```bash
sf data query --use-tooling-api --query "SELECT QualifiedApiName, Description FROM FieldDefinition WHERE EntityDefinition.QualifiedApiName = '<OBJECT>' AND QualifiedApiName = '<FIELD>'" --json \
  | jq -r '.result.records[] | .Description // "NULL"'
```

The retrieved field's `<description>` carries the same text. Nothing else the CLI shows you does:
`sf sobject describe` returns no description at all. Setup shows it only on the field detail page,
where the managed-component banner beside it says you may edit certain attributes, which reads as
permission.

**Why it matters.** In the recorded case the guarded field was a type field whose description also
named which of its values the package's own processing accepted. A new value would have sat outside
that list and produced records the package could not process, with a green deploy and a feature
quietly off. That outcome is an inference from the vendor's wording rather than something tested,
but the shape holds either way.

### Inline picklist or global value set: establish which before reasoning about either

**A subscriber's edits to a packaged global value set survive a package upgrade; an inline packaged
picklist carries no such guarantee.** Per the same packaging guide, an upgrade leaves a packaged
global value set's value labels and API names, its active and inactive settings, and its defaults as
the subscriber org has them, and adds none of the developer's new values; only the set's own label
follows the upgrade.

A field on a global value set names it in a `<valueSetName>` element; an inline picklist carries a
`<valueSetDefinition>` instead, and the replace semantics apply to it directly. List the org's sets
with `sf org list metadata`, where `installed` marks a packaged set and `unmanaged` one of yours:

```bash
sf org list metadata --metadata-type GlobalValueSet --json \
  | jq -r '.result[] | "\(.fullName)  |  \(.manageableState)"'
```

Two other routes look equivalent and are not:

- **`sf project retrieve start -m "GlobalValueSet"` as a wildcard returns only the unmanaged sets**,
  with exit 0 and no warning. In one production org that was eight of 18. A diff against it reports
  "no drift" on exactly the packaged sets most likely to have drifted, so name each set with
  `-m "GlobalValueSet:<fullName>"` and count the files that came back against the listing.
- **Tooling `GlobalValueSet` keeps a deleted set's row**, with the live set's `DeveloperName`,
  `ManageableState` reading `unmanaged`, and no field to filter it by. In one sandbox it returned 19
  rows for 18 sets.

---

## Reading the values you are about to change

### On an unrestricted picklist, a retrieve cannot see the inactive values

**A metadata retrieve and Tooling `CustomField.Metadata` leave an unrestricted picklist's inactive
values out entirely.** So a value a deploy deactivated reads as deleted, and a new value deployed
inactive reads as never created. Measured in a sandbox: both listed two values for an unrestricted
custom picklist, while the field's Setup page listed those two as active plus six inactive, four of
them written by the deploy being checked.

**A restricted picklist's retrieve does carry its `<isActive>false</isActive>` values**, which is
how this got past a check: a restricted field retrieved for comparison showed its inactive values,
and the conclusion drawn was that the deploy on the unrestricted field had deleted values it had in
fact deactivated. `sf sobject describe` and `PicklistValueInfo` list active values only, so neither
settles it.

**Read an unrestricted picklist's inactive values from the field's Setup page**, whose Inactive
Values list also stamps each value with a Modified By time, showing which deploy last touched it.
The Classic page renders without the Lightning frame, so a browser automation tool can read the
Values and Inactive Values tables as text:

```
https://<your My Domain>/<field Id>?setupid=CustomObjects&isdtp=p1
```

Take the field Id from a Tooling query on `CustomField` filtered by `DeveloperName` (the API name
without its namespace or `__c`), and pick the row whose `TableEnumOrId` is your object: the object's
name for a standard object, its Id for a custom one.

### A record type's retrieve omits its picklist assignments

`sf project retrieve start -m "RecordType:<Object>.<RecordType>"` returns the record type without
its `<picklistValues>` blocks, so a restricted record type looks unrestricted. Retrieve the whole
object with `-m "CustomObject:<Object>"`, which includes the complete `<picklistValues>` per record
type. Special characters in those blocks' `<fullName>` values are URL-encoded rather than
XML-encoded: `&` is `%26`, `(` is `%28`, and `,` is `%2C`.

**To see exactly what one record type's picker offers, call the UI API from a signed-in browser
session**, for example through a browser automation tool's JavaScript execution:

```js
await fetch(`/services/data/v65.0/ui-api/object-info/<OBJECT>/picklist-values/${recordTypeId}/<FIELD>`).then(r => r.json())
```

The same path returned `NOT_FOUND` through `sf api request rest` in the one test made, so only the
browser route is verified. **To prove a record-type deploy left the per-record-type assignments
intact, check a field whose per-record-type list is shorter than its active value set.** In the
recorded check a field had 24 active values and 22 for the record type, so seeing 22 proved the
assignments intact where 24 would have shown them wiped.

---

## Comparing value sets without the comparison misleading you

Each of these produced a wrong conclusion in a real comparison, and none of them looked like an
error at the time.

- **Decode XML entities before diffing.** Field XML stores `&amp;` where a describe returns `&`, so
  a value containing `&` fails to match itself, and under replace semantics "absent from the file"
  reads as "shipping this switches it off." In the recorded case that produced a confident finding
  that a change would deactivate three live values, one of them held by 208 production records, and
  it reached a colleague and a filed bug before anyone noticed that **all three were the only values
  in the list containing an ampersand**. Treat "everything that differs shares one punctuation mark"
  as an encoding artifact until disproved. `&lt;`, `&gt;`, `&quot;`, and `&apos;` (or `&#39;`) occur
  too, so decode with an XML parser rather than a single `sed`.
- **Strip carriage returns and a byte-order mark from both sides.** On Windows, Python's `print()`
  writes CRLF when redirected to a file, so its list differs from `jq` output by one trailing byte
  on every line. A 29-value source list against an org's 29 active values came back "29 only in A,
  29 only in B" when the two matched exactly. `PYTHONUTF8=1` does not change newlines;
  `sys.stdout.reconfigure(newline="\n")` does.
- **Refuse an empty side and a zero overlap.** Two empty files compare as identical, and a
  line-ending mismatch makes two identical lists look disjoint. Neither looks like an error, which
  is the problem: a broken comparison reads as a finding.
- **Measure the picklist in every org before naming which one drifted.** In the recorded case a work
  item's own text said the stale values lived in one sandbox. That came from an earlier artifact
  rather than a measurement, it reached a tester, and one describe per org showed a different
  sandbox held them.
- **Know which org a describe came from.** A describe cached by a script that inherited the CLI's
  default org answers about whichever org that was, so a guard built on it can approve exactly what
  it exists to catch. Compare against source, and have any fetcher print the org it used.

A method that handles the first three: take the file's side with an XML parser, which decodes
entities, and compare with a function that normalizes both sides and refuses a comparison it cannot
trust.

```bash
# Active values in a field, global value set, or standard value set file, entities decoded
python3 - path/to/My_Field__c.field-meta.xml > source.txt <<'PY'
import sys, xml.etree.ElementTree as ET
sys.stdout.reconfigure(newline="\n")
m = {"m": "http://soap.sforce.com/2006/04/metadata"}
root = ET.parse(sys.argv[1]).getroot()
values = (root.findall(".//m:valueSetDefinition/m:value", m)
          + root.findall("m:customValue", m) + root.findall("m:standardValue", m))
for v in values:
    if v.findtext("m:isActive", "true", m) != "false":
        print(v.findtext("m:fullName", "", m))
PY

# Active values in the org
sf sobject describe --sobject <OBJECT> --json \
  | jq -r --arg f '<FIELD>' '.result.fields[] | select(.name == $f) | .picklistValues[] | select(.active) | .value' > org.txt

cmpvals() {
  local a b both
  a=$(sed 's/^\xEF\xBB\xBF//; s/\r$//' "$1" | LC_ALL=C sort -u)
  b=$(sed 's/^\xEF\xBB\xBF//; s/\r$//' "$2" | LC_ALL=C sort -u)
  if [ -z "$a" ] || [ -z "$b" ]; then echo "REFUSED: one side is empty"; return 2; fi
  both=$(LC_ALL=C comm -12 <(printf '%s\n' "$a") <(printf '%s\n' "$b") | wc -l)
  if [ "$both" -eq 0 ]; then echo "REFUSED: zero overlap; check encoding and line endings"; return 3; fi
  LC_ALL=C comm -3 <(printf '%s\n' "$a") <(printf '%s\n' "$b")
}
cmpvals source.txt org.txt
```

`comm -3` prints values only in the file at the left margin and values only in the org indented by a
tab. **The indented ones are what the deploy would switch off.** The parser takes each value's API
name (`fullName`), which is what a describe's `value` holds. Both pieces were tested on synthetic
input (an `&amp;` value, an inactive value, and CRLF org output), not against an org.

---

## After you remove, deactivate, or rename a value

- **A validation rule naming a value the picklist no longer offers deploys clean, and still fires on
  the records that hold it.** `ISPICKVAL` compares the stored value, so the clause is false for
  every new record, since nothing can select the value, and true on every existing record still
  holding it. Measured in a sandbox: a record holding an inactive value evaluated `ISPICKVAL` on
  that value true, and the rule refused to save it. So a clause that looks dead can be the only
  thing gating legacy rows, and trimming such clauses released records that had been blocked.
  **Before trimming one, count the records holding the value** with the `GROUP BY` in *What `false`
  does buy you*.
- **A record type naming a value the org lacks fails the deploy outright**, with
  `Picklist value: <value> in picklist: <field> not found`. Do not generalize from that to formulas,
  which deploy clean.
- **Read a flow decision's `conditionLogic` and operator direction before calling a stale value in
  it a defect.** An ANDed list of `NotEqualTo` conditions is an exclusion gate: a stale value in it
  holds back only the records still carrying that value, and dropping it lets them through. An ORed
  list of `EqualTo` conditions is an inclusion gate and fails the other way, since a value it omits
  keeps that value's records from ever matching.
- **When you rename a value, grep every validation rule, formula, and flow for the old one** rather
  than trusting the next deploy to surface it. While two orgs are mid-rename, have a rule name both
  vocabularies, since dropping either side uncovers one org.
- **When automation copies a value from one picklist to another, change both value sets in the same
  change.** If the target is restricted, a source value missing from it fails the insert with
  `INVALID_OR_NULL_FOR_RESTRICTED_PICKLIST`, and an all-or-none insert saves none of the batch.
  Measured with an all-or-none Apex insert in a sandbox; the flow that does the copying was not run,
  and Salesforce Help says a schedule-triggered flow then retries the records that succeeded, so a
  flow run's final result can differ.

---

## Dependent picklists

- **The dependency lives on the dependent field only.** `<controllingField>` and `<valueSettings>`
  are stored on the dependent field, so the controlling field's file says nothing about it. In the
  recorded case a routine sandbox sync that carried the controlling field without the dependent one
  left the org with no dependency at all, and reported success. Deploy the two as a pair.
- **A picklist can be dependent and controlling at once.** The often-repeated statement that a
  custom picklist can be a dependent picklist or a controlling field, but not both, did not hold: a
  three-level chain (A controls B, B controls C) deployed, the describe reported
  `dependentPicklist=true` with the expected `controllerName` on both lower levels, and the UI left
  each level disabled until its parent was chosen, verified in two sandboxes. So do not flatten a
  genuine three-level hierarchy into two, or derive the top level with a formula, on the strength of
  that statement.
- **A green deploy cannot tell a correct dependency from one that filters to the wrong values**, so
  decode `validFor`. Each dependent value's `validFor` is a base64 bitmap over the controlling
  field's values, in the order the describe returns them, one bit per value, most significant bit
  first:

```bash
sf sobject describe --sobject <OBJECT> --json > describe.json
python3 - describe.json <CONTROLLING_FIELD> <DEPENDENT_FIELD> <<'PY'
import base64, json, sys
fields = {f["name"]: f for f in json.load(open(sys.argv[1], encoding="utf-8"))["result"]["fields"]}
ctrl = [v["value"] for v in fields[sys.argv[2]]["picklistValues"]]
for v in fields[sys.argv[3]]["picklistValues"]:
    bits = base64.b64decode(v.get("validFor") or "")
    ok = [c for i, c in enumerate(ctrl) if i // 8 < len(bits) and bits[i // 8] & (0x80 >> i % 8)]
    print(v["value"], "->", ", ".join(ok) or "(no controlling value)")
PY
```

Write the describe to a file and pass its path: piping `sf` into `python3 - <<'PY'` silently drops
the pipe, because the heredoc is the script's standard input. The snippet is written for a picklist
controlling field and was tested on synthetic input, so spot-check one value in the UI before
trusting it for a whole field.

---

## Moving a picklist onto a global value set

**A deploy cannot move an existing picklist with its own values onto a global value set.** A
check-only deploy of a new set plus the field rewritten with `<valueSetName>` validated the set and
failed the field with `Cannot change which global value set this picklist uses.` The documented
route is the field's **Promote to Global Value Set** button in Setup
([Make Your Custom Picklist Field Values Global](https://help.salesforce.com/s/articleView?id=platform.fields_promote_picklists.htm&type=5)).
Per that article it cannot be undone short of deleting and re-creating the field, it takes only a
restricted picklist of up to 1,000 values (active and inactive together), and it cannot promote into
a set that already exists.

- **The button is on the field's Edit page** (Classic URL `/<15-character field Id>/e`), not the
  detail page Lightning Object Manager opens.
- **Promote by hand in every org before any deploy carrying the promoted field reaches it**,
  including any org your pipeline validates against. A set that reaches an org first, for example
  through a sync that excluded the failing field, blocks that org's promotion, since a field cannot
  be promoted into an existing set.
- **Take the set's name from a retrieve, never from a deploy result.** The
  [GlobalValueSet reference](https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_globalvalueset.htm)
  says a set created in API version 57.0 or later has `__gvs` appended to its developer name. In the
  recorded orgs, sets created in 2026 carried the bare name in a retrieve and in Tooling
  `DeveloperName`, while a deploy result listed the same set with `__gvs`. Check it in each org,
  since one promotion settles nothing about the next.
- **Check the sort setting afterwards.** One promotion came back `<sorted>false</sorted>` where the
  inline picklist had been `<sorted>true</sorted>`.
- **Deleting a set that a deleted field used fails until that field is erased** from the object's
  Deleted Fields page:

  ```
  This global picklist is used by 1 or more custom fields. Remove the usage and try again. : <Object>:<Field Label>.
  ```

  Confirm a set is gone with `sf org list metadata` or Setup's Picklist Value Sets page, never
  Tooling.
- **A custom metadata type picklist cannot reference a global value set at all.** The binding fails
  with `Global picklists are not supported on this object`, while the same deploy creates the set
  and the type. Give the metadata type its own restricted list mirroring the set, and say in the
  field's description that it is kept in step by hand.

---

## Extend the packaged set, or add a field of your own

**The description decides it, not the namespace and not the restriction.**

- **The description carries a do-not-change note**: leave the field alone. Add a field of your own,
  or ask the vendor whether the change is safe. The field drives package behavior, so a value
  outside the vendor's list produces records the package cannot process.
- **No such note**: extending the packaged set is legitimate. Deploy the retrieved file with your
  value added, carrying every existing value, after diffing it against every org it will reach.

**A field of your own is not free, so do not say it costs nothing.** In the same change it needs
field-level security on the permission sets of the people who use it, a place on the page layout or
in a Dynamic Forms region, and a description of its own. It is usually still the right call against
a guarded field; the point is to price it honestly.

**Never reuse the managed field's base API name.** A subscriber `Status__c` beside a packaged
`ns__Status__c` can collide. In the recorded case the package's code resolved field names without
the namespace, so the subscriber field shadowed the managed one; where the types differed, every
update through the package's trigger threw an error naming neither field, while inserts succeeded,
which made the defect easy to miss. That is one package's behavior, and whether another resolves
names the same way is not established, but a suffix (`Status_Detail__c`) costs nothing, and the
page-facing label can stay as you want it.

---

## The case behind this skill

Asked whether a new status could be added to a packaged status picklist, a session ran
`sf sobject describe`, read `restrictedPicklist=true` in a managed namespace, and recommended
against it because the field was restricted and managed. The recommendation happened to be right
and every reason given was wrong: the restriction does not bar an admin, the packaging guide
explicitly permits subscriber value edits, and the field's actual guard, the do-not-change note in
its description, was never read because a describe does not return it. The project's written rule
on replace semantics had been cited, correctly, inside that same wrong answer, which is why the
order of checks in this skill starts with the description.
