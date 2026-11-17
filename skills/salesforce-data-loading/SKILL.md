---
name: salesforce-data-loading
description: "Bulk data loads in Salesforce. TRIGGER when: designing or running an sf data import/upsert/update, building a load CSV, counting rows in a CSV export, checking loaded records against a source file, loading records owned by a departed user, or DUPLICATE_VALUE / INACTIVE_OWNER_OR_USER / LineEnding / 'Field name not found' / Too many SOQL queries errors. Not for deleting records."
metadata:
  version: "1.1"
  license: MIT
---

# salesforce-data-loading

The field flags to read before designing a load, the CLI flags and permissions the job needs, the
ownership pattern for departed users, how to pre-flight a load and check it against its source, and the
traps that report success while doing the wrong thing.

Point-in-time: measured on Salesforce orgs during 2026. Verify against your own org before asserting
any of it as current fact.

---

## Set the audit fields on ANY import of records that already existed

**Default to setting `OwnerId`, `CreatedById`, and `CreatedDate` from the source on every load that
represents something which existed before it**: a migration, a backfill, a re-load of records that did
not land, an import from another system. Not only the departed-owner case below.

Records that carry the loading user and the load date sit visibly apart from their peers, and they
misreport who did the work and when to anyone reading the record or reporting on it.

**Decide it BEFORE the insert, because audit fields cannot be retrofitted.** `CreatedById` and
`CreatedDate` are writable **only on insert**, and only with the **Set Audit Fields upon Record
Creation** user permission. They are `updateable=false` forever after, so the only way to correct them
later is to delete the record and insert it again. `OwnerId` is the exception: it is updateable, so
owner alone can be fixed after the fact.

**Pre-flight, one line, before building the load file:**

```bash
sf sobject describe --sobject <API> --json | jq -r '.result.fields[] | select(.name=="CreatedDate") | "createable=\(.createable) updateable=\(.updateable)"'
```

`createable=false` means the permission is not held and the audit fields will silently default to the
loading user and the load date. **Do not assume the permission is still on because a previous load used
it** — it is commonly enabled for a migration and turned off afterwards, and one production org was
found in exactly that state for a full administrator, months after a migration that had used it.
Granting it is a permission-set change and belongs in the plan, before the load rather than after.

**What it costs to skip:** in the recorded case two records loaded without it carry the loading user
and the load date against 9,862 peers carrying the real ones. Owner was corrected afterwards by update;
the audit fields were not correctable at all.

**Take the owner from the source's owner field, not from whoever drafted the document.** A source
system can record both, and they disagree more often than you would guess: on one contract system's
export the drafter differed from the owner on about two thirds of documents. Where an earlier migration
already loaded records from the same source, sample them to see which field they followed. In the
recorded case, on 1,030 sampled records where the two differed, `CreatedById` matched the owner field on
943 and the drafter on none. The earliest authoring event is still the right source for the creation
date; it is the wrong source for the owner.

**When unsure whether a population should load at all, holding it back is the reversible choice.**
Loading commits to audit values that cannot be corrected without a delete and a fresh insert, while a
population held back can be loaded later with its audit fields intact. In the recorded case declined and
cancelled documents from a migrated system stayed out for that reason, together with the facts that no
status mapping for them could be derived and nothing downstream depended on them.

---

## Assigning records to an inactive user

Some loads need a record **owned by a person who has left**, for instance a migrated agreement whose
requestor is a departed employee. This is an **ownership** problem rather than a writable-field one.

The mechanism worth recognizing: where a display field is a formula that falls back to the record
**Owner** when a lookup is blank, and the load leaves that lookup blank, the only way to preserve the
true historical person is for that now-inactive user to own the record. **Read the fallback direction
precisely, because it also governs the reverse case:** transferring such a record *away* from the
departed owner silently rewrites the displayed person, which is why deprovisioning should not blanket
reassign closed records.

**Two user permissions are required together:**

- **Set Audit Fields upon Record Creation** lets an INSERT set `CreatedById`, `CreatedDate`,
  `LastModifiedById`, and `LastModifiedDate`.
- **Update Records with Inactive Owners** lets `OwnerId` be, or become, an inactive user.

**Prefer the INSERT path.** With both permissions, a single insert can set `OwnerId` directly to an
**inactive** user *and* backdate the audit fields, including `CreatedById` and `LastModifiedById` to
that same inactive user, so "Created By" reads as the real person. No activate-then-deactivate round
trip is needed: create the user inactive up front and set everything at insert. Verified on a load of
9,838 records.

**The UPDATE and transfer path is the one that fails, and its errors mislead:**

- Transferring an existing record to an **already-inactive** user via update returns
  `INACTIVE_OWNER_OR_USER`.
- Transferring to a user that lacks read on the object returns `TRANSFER_REQUIRES_READ`, which is easy
  to miss.
- So handing an *existing* record to a departed person means: create the user **active**, grant it
  object access, set `OwnerId`, then **deactivate**. Ownership persists on inactive users. For a fresh
  load, skip all of that and use the insert path.

Two practical notes when creating placeholder users for this. **Reuse any pre-existing inactive user
for that name rather than duplicating it**, found with a name-only lookup across both active and
inactive. And **watch compound surnames**, since a name like "Jane Doe-Smith" can normalize to
"Jane Smith" and miss on a later run; alias it.

**Load mechanics.** Hold a bypass permission set granting whatever custom permission your
record-triggered flows check, so the load does not fire a notification burst, then remove it after. Set
Audit Fields does **not** override validation rules, so a rule that requires a field for a given status
still fires; satisfy it in the data.

**The bypass matters on an update as well as an insert.** A before-save flow that stamps fields from
configuration (a category, a set of approval flags) re-stamps them on every save by anyone who lacks
the bypass, so a bulk update run without it silently rewrites those fields from the current
configuration. Check who holds the bypass before the job rather than assuming the loading user does;
in the recorded case nobody in production held it.

**A bypass covers only the automation that checks it.** Flows a vendor or package delivered, or anyone
built without that check, fire regardless of your custom permission. List the active record-triggered
automation on the object, deactivate what the bypass does not reach for the load window, and reactivate
it after. The reverse also holds: a bypass that suppresses your own automation can suppress something
the load depends on, such as a handler that creates related records the rest of the org expects. Decide
per load which automation must fire.

**A flow that fills a blank date when a record reaches a status takes the load date.** Where automation
stamps a date (an actual close date on a closed record, say) whenever the status matches and the date
is blank, inserting records at that status with the date column empty stores the day of the load. In
the recorded case three records took the load date instead of their real execution dates. Supply the
real date in the load file; an update afterward also sticks, since the field is no longer blank.

---

## Do not ask for a value the org can already tell you, and score the answer before loading

**When a load needs a value nobody has decided, look first at what comparable records already carry.**
In the recorded case that answered two of five outstanding groups without anyone ruling on them: 227
records took a value because the same counterparties carry it on 145 of the 159 that resolve elsewhere,
which also retired a standing request for a new picklist value that had already been put to two people.
Comparable usually means same counterparty, same project, or same document type, and the query is a
`GROUP BY` over the records that are already populated.

**Band the answer by how decisive the evidence is, and load only the strong band.** The same technique
on a second group resolved 318 of 390, but the org genuinely used both values, so a single answer for
the group would have been wrong. Splitting by margin loaded 237 where the evidence pointed one way
decisively and held 81. The held rows clustered on four counterparties whose work spans both
categories. **That clustering is the tell that the split is real variation rather than noise**, and a
uniform answer there would be a coin flip wearing evidence.

**Score a candidate rule against the records that already carry the value, and let the number decide.**
A rule that reproduces a third of the known-good answers is a rule to abandon, not to tune. **When every
candidate rule scores badly, though, suspect the input before the rules.** In the recorded case five
rules for reconstructing a cumulative contract total each scored at best 32% against the values
production already held, and the conclusion drawn, that no chain could be computed, was wrong. The
consolidated extract the rules ran on carried one value column, while the raw export carried three (a
change in price, a contract value, and a total contract value), and the single column meant the running
total on a document with a price change and the increment on one without. With the rule the business
then supplied, that the field holds each document's own value (the change in price where there is one,
otherwise the contract value), the score against 440 values an earlier migration had written was 98.9%,
and no accumulation was needed at all. **So list a source file's columns, in the rawest form you can
get, before deriving anything from it.**

**Re-measure a stated blocker before you treat it as one.** One field sat recorded as blocked on
records that did not exist, measured when production held 108 of them. It held 1,103 four weeks later
and 788 rows linked on exact name match, so the block had quietly lifted and the note describing it had
not. **A blocker written down weeks ago is a claim with a date on it.**

**A decision can arrive as a data change, too.** In the recorded case a naming question was settled by
three records being renamed in the org, with nothing said on either work item that tracked it. Query
the org before asking anyone a second time.

---

## Before bulk-changing a record's type, compare what each type drives

When a type field (a record type, or a picklist that selects configuration) decides approval routing,
required reviewers, or defaults, a bulk change of it moves the records under a different configuration,
and that is the part the requester is least likely to have looked at. A requester naming the target
type settles what they want, not whether the records fit the business's definition of that type.

So read both types' definitions and both configurations before running, explain any difference to the
requester, and put any conflict to them with the definition in hand. Do not count on the org to hold
the definitions: in the recorded case the description field on the type configuration records was blank
on most of them, and the business's definitions lived in a spreadsheet.

---

## Pre-flight a load against what the org already holds, not only the file

**The person who sends the file might already have entered part of it by hand.** In the recorded case
14 records were entered by hand in production the day before the file describing the same items
arrived, and the file's own duplicate check passed cleanly while 14 collisions sat in the org. So check
every row against the org's existing records on whatever combination makes a record unique to the
business (a location plus an item, say), not only within the file.

**A join on one code is not enough.** A part-number join found seven of those 14, because the
hand-entered records carried a prefix, a model number where the file had the full code, the code in the
record name with the code field blank, or a one-character difference. Match on name and code in both
directions, band the matches by confidence, and refuse to proceed unless every row lands in the
confident band, so that no unmatched row can fall through as new.

**Records entered during a migration carry none of its keys.** Records people create directly in the
org while a migration from workbooks is still running have no migration key, no source dates, and a
free-text name, so a key match reads the workbook row as new and loads a duplicate. Match on business
attributes as well (counterparty, location, size) and compare the titles of attached files.

**For records keyed by an external id, intersect the incoming keys with the org's before deciding
whether the list is a load or a move.** It has gone wrong in both directions: a file that read as a
delivery list was 1,525 records already held at another location, and a list of items "taken from" one
location matched nothing in any org and had to be created. An upsert keyed on an external id updates
existing records silently, so the intersection is the only place the difference shows.

**A normalized match key can hide missing children.** A key that drops a child suffix and ignores zero
padding reads every child document as already loaded once its master is, while the org holds only the
master. Count the documents, not the keys.

**A load that sets numbers directly bypasses whatever allocates them.** Where custom automation hands
out the next number from a registry or counter object (the maximum plus one), a load that writes numbers
onto records without writing the registry leaves numbers the allocator will issue again. In the recorded
case two loads put records on numbers already issued that way. Bring the registry up to date after each
such load, and before one, check every new number against the records as well as the registry.

---

## Reconciliation loads: fill blanks, never overwrite a conflict

**Never auto-load a conflict during a reconciliation import; only ever fill a blank.** People correct
migrated records by hand from the day the migration lands, and an overwrite discards that silently. In
the recorded case a former-name field already held a fuller value than a blind re-load would have
written. So diff against the existing external ids and insert only what is absent rather than
upserting, and route every conflicting value to a person.

**An exact-name crosswalk leaves records unlinked for good.** A lookup resolved at load time by matching
names exactly came back blank on migrated records once a later change to the name form (adding an "Inc"
suffix) broke the match, and nothing re-resolves it, because no back-linking pass exists. When relinking
after the fact, only touch rows where the crosswalk was confirmed or where the legacy name resolves to
exactly one record.

**Fuzzy matching must exclude a candidate whose number, roman numeral, or compass direction differs,
however high it scores.** In the recorded case pairs that differed only by a trailing roman numeral
(shapes like `Holdings I` and `Holdings II`) scored 97%, and a pair differing only by `Southwest`
against `Southeast` scored 95%. Those are separate legal entities, and the differing characters are
exactly what string similarity treats as noise.

**Conversely, do not discard borderline candidates; flag them.** Dropping them lost four true matches
that were typos in the opening characters, shapes like `A&B Partners` against `A and B Partners`.

**Match against every name the record keeps**, a legal name or a former name as well as `Name`, where
the object carries them.

---

## Checking a load against its source: how the comparison lies

**A comparison that silently drops what it cannot match reports agreement where it should report
ignorance, and it fails in the reassuring direction every time.** Two confident wrong answers came out
of one session's own comparison code during migration QA. A tester caught the first; testing the check
itself caught the second.

**Joined on the display name, so mismatches vanished.** In the recorded case 173 migrated records were
matched to their source workbook by record name, skipping any record whose name the workbook lacked. Of
those, 21 carried names the workbook did not have, so they were never compared, and the result was
reported as "exactly one status mismatch in 173" from a check that had examined 152. The real number
was five, and four of them were in the skipped set. The wrong figure reached a work-item comment before
it was corrected.

**A clean result from a check asking the wrong question.** Diagnosing a record attached to the wrong
parent, a test of whether a workbook's parent-reference value matched more than one parent name
returned a reassuring 0 of 643. It was meaningless: the references carried a stable id, not a name, so
nothing was ever ambiguous, and the whole root-cause theory was wrong. It had already been filed as a
bug with an exposure figure attached. Opening the workbook cell settled it at a glance.

Both errors share one root: **a cause inferred from what the org looks like, without opening the input
that produced it.** So:

- **Join on the stable key** (an external id, a migration key, a business identifier), never a display
  name. A name is exactly the field a migration is most likely to have rewritten.
- **Never skip past an unmatched row.** Count both unmatched sides and print them. "152 of 173
  compared, 21 uncomparable" is a finding; "one mismatch" is a lie by omission.
- **Test the comparison against a case already known to fail before believing a clean run.** Running
  the one known-broken group through the check would have reported it as fine, in one step.
- **Distrust a zero you just produced**, especially one that ends an investigation. Ask what the check
  would look like if it were broken, and whether you could tell the difference.
- **Open the source input before naming a cause.** The org shows the symptom; only the input shows why.

---

## `sf data ... bulk` needs `--line-ending LF` on Windows

The CLI defaults the *job* to CRLF from the host OS, so an LF data file is rejected outright:

```
ClientInputError : LineEnding is invalid on user data. Current LineEnding setting is CRLF
```

Nothing is applied. It fails loudly, which is the good case; the trap is reading it as a data problem
and editing the CSV. If your generators write pure LF, the flag is needed every time rather than
occasionally.

---

## Pass `--column-delimiter COMMA` too, or text full of pipes changes the delimiter

Without the flag, `sf data import bulk`, `sf data upsert bulk`, and `sf data update bulk` **guess** the
delimiter: they count each candidate (`,` `|` `;` tab `^` `` ` ``) outside quotes across the file's
first five lines and use the most frequent (`detectDelimiter` in `@salesforce/plugin-data`'s
`bulkUtils.js`, read at sf CLI 2.157.8; only `delete` and `hardDelete` default to comma). So a file
whose text column holds more unquoted pipes than the file has commas is read as pipe-delimited, and the
job fails on the header and applies nothing:

```
InvalidBatch : Field name not found : Id,My_Comments__c
```

It bites a **narrow** file hardest, because the header contributes so few commas. In the recorded case
a two-column update (`Id` and a comments field) of 1,550 records, each comment carrying eight ` | `
separators, scored five commas against 32 pipes in its first five lines and failed on its first job. An
eight-column load of the same records hours earlier had passed at 35 commas to 32 pipes, and one more
separator per comment would have tipped it too (a tie goes to the comma). Python's `csv` writer quotes
a field only when it needs to (a comma, a quote, or a line break), so the pipes went out unquoted.

Like the line-ending trap it fails loudly, so the risk is editing a good CSV to chase it. Put the flag
beside `--line-ending LF` on every bulk insert, upsert, and update:

```bash
sf data import bulk --sobject <API> --file <file.csv> --line-ending LF --column-delimiter COMMA
```

---

## Blanking a field in a bulk update needs `#N/A`

An empty cell means "leave it alone", and the job reports success either way. This is the quiet twin of
the line-ending trap and the worse one, because nothing in the output distinguishes "wrote your value"
from "ignored your column".

Verified on `ContentVersion`: five rows with empty cells returned `processed=5 ok=5 failed=0` and **all
five still held their old values**; the same five rows with `#N/A` cleared to NULL.

So a success count is not evidence a field was cleared, and **a clearing load has to be confirmed by
reading the records back.**

It cuts the other way too, and that half is useful: an empty cell is how you update one column without
disturbing the rest of the row, so a load file should carry only the columns it intends to write.

---

## Count CSV rows with a parser, never `wc -l`

Long-text fields carry embedded newlines, so a CSV holds more physical lines than records. An
881-record export spanned **1,015 lines**.

Line-counting reports a surplus that does not exist, and it errs in the alarming direction: the count
reads as a defect in the export or the load, so the reflex is to go hunting for rows that were never
there. It bites wherever a row count is the evidence — sizing a load file, reconciling an export
against a `COUNT()`, or confirming what a job processed.

```bash
python -c "import csv,sys; print(sum(1 for _ in csv.reader(open(sys.argv[1], newline='', encoding='utf-8'))) - 1)" <file.csv>
```

Pass the path as `sys.argv[1]` rather than inlining it. A Windows path inside the `-c` string makes
Python read the `\U` of `C:\Users` as a unicode escape.

---

## Reading a source workbook: the traps are in the spreadsheet, not the org

**Read row counts, not sheet dimensions.** One tab reported a used range of `A1:S3135` and held 141
populated rows; the rest was blank formatting.

**Resolve columns by header name, never by position.** In one workbook the tabs disagreed: one had a
PO number in column 8 and country of origin in column 11, the next swapped them, a third had no origin
column, and the header row sat on a different line in each tab. A builder that hardcodes column numbers
writes the wrong values into the right fields with nothing erroring.

**A cell fill can mark which columns are real data.** On one workbook a fill color marked exactly the
columns the sender had filled in, and all three of its bad columns sat outside that fill. Those three
shapes are worth checking on any workbook:

- **A pair of limits swapped** (a maximum and a minimum quantity) and constant across every row. The
  org's existing data settles the direction, since a minimum is always at or below its maximum.
- **A column not row-aligned** with the column it should describe, holding values that belong to
  another location, its data validation pointing at `#REF!`.
- **One cell holding two fields**, such as a location type and a number together, spelled differently
  from the org's value.

---

## Read `unique` on the describe before designing any load that repeats a value

Not just `updateable` and `length`. A unique field accepts the first record and rejects every other
with `DUPLICATE_VALUE`, and because a bulk job reports that per record rather than up front, the
constraint surfaces only after thousands of rows have been attempted.

In the recorded case a file backfill checked `createable`, `updateable`, and `length`, read all three as
green, and loaded 18,513 records. **8,604 failed**, because the external-id field was `unique=true`
while 6,412 source documents carry more than one file, one of them 56. **The flag decided the whole
approach and was the one not read.**

**A tracing or grouping field is almost always wrong as Unique.** Repeated values are the point, and
they are what lets the field double as a duplicate indicator. The original design had made both tracing
fields Unique on the assumption of one file per document.

Removing Unique costs the upsert key, since a non-unique external id fails an upsert whenever more than
one record matches, so such loads have to key off `Id` instead. Decide that consciously rather than
discovering it.

---

## An external id decides the shape of a hierarchy load

With a real external id on the object, a parent-child hierarchy loads as **one** file, carrying the
parent through the relationship (`Parent__r.My_External_Id__c`), and the load becomes a **re-runnable
upsert**. Without one it needs a multi-pass insert, parents before children with each parent resolved
by name, and where `Name` is not unique a re-run duplicates silently and a parent name then matches two
records. Check for an external id before you design the passes.

---

## Automation can store something other than what the job reported loading

A trigger or validation in a managed package, or your own before-save automation, can accept a value,
report success, and store something else. Three shapes, measured on one managed package's objects:

- **An insert at a given status overwrote a date the file supplied.** All 141 rows of an insert carried
  a historical install date with the status set to installed, the job reported 141 of 141 successful,
  and every record came back holding the day of the load. A plain update afterward stuck, so the load
  became two passes: insert, then update the date from the Ids the insert returned.
- **A value coerced silently on insert was rejected on update.** A quantity of 30 on an item the package
  tracks one unit per record came back as 1 on all three test records with the job reporting full
  success, while an update carrying a quantity failed with `FIELD_CUSTOM_VALIDATION_EXCEPTION`. Leave
  such a column out of the load file entirely, or every re-run of an upsert fails on it, and tell
  whoever asked for the load what the coerced value means downstream (in that case, availability
  counted records rather than units).
- **A sandbox defaulted a field that production required.** The identical 70-row file loaded 70 of 70
  to a sandbox and failed all 70 in production on a required field the sandbox had filled in on its own,
  so the column could be absent from the file and still come out populated in the sandbox. It failed
  safely, but it cost a full round trip and read as a data problem rather than an org-parity one. Put
  every required column in the file explicitly rather than relying on either org's behavior, and treat a
  clean sandbox load as evidence about the sandbox only.

**The rule the three share: read the fields back from the org, never the job summary.**

---

## A field locked after insert: resolve it before the load

A managed package can reject any change to a field on an existing record, which makes that field
insert-only in practice. A bulk update that changes it fails the row with
`FIELD_CUSTOM_VALIDATION_EXCEPTION` and **applies nothing else in that row**: a comments field in the
same row was left unchanged too. `sf data update bulk` surfaced it only as `FailedRecordDetailsError`,
and the per-row error came from the job's failed results (the request is in the per-object bulk limits
section).

**So resolve the value from the most specific identifier the source has before the insert**, such as a
product code, never from a single attribute it was inferred from.

**The only correction afterward is a delete and a fresh insert, and the delete can take child records
with it even when the describe says it will not.** The new record gets a new Id. In the recorded case
the child relationship reported `cascadeDelete=false` and `restrictedDelete=false`, and deleting two
parent records in production still sent their child transaction records to the Recycle Bin in the same
second (`IsDeleted=true`, found with `sf data query --all-rows`). The package's own triggers were the
only delete handlers on the object, so they are the likely cause; that is inferred, not traced. A
describe's `cascadeDelete` speaks for the platform relationship only, not for what a trigger does on
delete, so plan on the re-inserted record starting with no history.

---

## Some objects write their own child records when you update them

A managed package, or your own after-save automation, can write related records as a side effect of an
insert or a field update. The job summary says nothing about them, and a load that also writes them by
hand records the event twice. Measured on one managed package's inventory objects:

- **A quantity update wrote one adjustment record per changed record**, carrying the signed change (new
  minus old), the parent, the running user as Created By, and that day's date. A record whose quantity
  did not change got none, and an update of a different field wrote none. So a stock count is a plain
  quantity update, and an adjustment written by hand for the same change would sit beside the
  package's own. In production a 38-record update carrying 35 quantity changes produced 35 adjustment
  records, one for one, and none on its three location-only rows.
- **A location change wrote a pair per record**, a transfer at quantity -1 and a receipt at +1, with the
  from and to locations each populated on only one of the two rows, so read the pair, never one row. The
  source location's rollup decremented, reversing the move restored it exactly, and the destination's
  rollup row was created automatically. Put a small batch through before a large one.
- **An after-save flow that creates a child on insert** means that child belongs out of the load file. A
  load that creates parent records and also loads the child creates two.

**So check the children when you read the records back**: query them by parent and `CreatedDate`, and
expect exactly one (or one pair) per changed record, carrying that change.

---

## Per-object bulk limits: a trigger that queries per record caps the job size

A trigger that spends roughly one SOQL query per record, plus a small constant, exceeds the
per-transaction ceiling on a 200-record chunk and fails the whole chunk:

```
CANNOT_INSERT_UPDATE_ACTIVATE_ENTITY:<namespace>.<TriggerName>: System.LimitException: <namespace>:Too many SOQL queries: 201
```

Bulk API 2.0 picks its own chunk size, so the only lever is how many records go into each job. Measured
on an `Id` plus one-field upsert against an object whose managed trigger behaves this way: 100 records
used 106 queries, and a 544-record job auto-chunked at 200 and failed **exactly 200 records** while the
other 344 went through. Re-running the same 544 as six jobs of 100 or fewer cleared all of them. A
production run of the same load at 100 per job failed nothing but still sat at 106 of 200 queries, so
100 works with about half the ceiling spare, not comfortably. Find out whether an object behaves this
way with a small job before the large one, and size jobs to it.

**The job status does not show the loss.** That job reported `Job Complete` with `Failed Batches 0`;
the 200 appear only in `Records Failed`. Read that column on every job, and pull the per-row errors
with:

```bash
sf api request rest "services/data/v65.0/jobs/ingest/<18-char job id>/failedResults/"
```

**No leading slash on the path**: with one, it returns `NOT_FOUND`, which reads as a wrong job id
rather than a wrong path.

Salesforce emails the running user once a transaction passes 50% of a governor limit, and on an object
like this that is the earliest signal available. Leave that email enabled for whoever runs loads rather
than switching it off on their user record.

---

## sfdmu can mis-resolve record types and lookups silently

Observed with the SFDX Data Move Utility (sfdmu): `RecordType.DeveloperName` and lookup fields resolved
to the org default or to null **with no error reported**, so the load "succeeded" and the data was
wrong. Resolve the record type and every lookup to explicit Ids yourself and load through the Bulk API.
Its exit code also reports success under `allOrNone:false` when rows failed, so count failures from its
output rather than trusting the exit code.

**A required lookup missing from an sfdmu simulation is reported only as a warning**, and becomes a
hard insert failure at load time. Treat any warning about a `nillable=false` lookup as an error.

---

## File loads: set the audit values on insert

`ContentVersion` honors backdated audit fields on **insert**, and a later update overwrites them, so
get them right in the insert. An **inactive** user can be a file's `CreatedById` but **cannot** be its
owner, unlike the custom-object insert path in the inactive-user section. Files over roughly 37 MB need
a multipart upload rather than a base64 body.

---

## If you generate import templates

Two conventions worth keeping whatever generates them.

**Templates are insert-focused, not update-focused.** Do not include the `Id` or "Record ID" column, and
do not add comments framing the template as "leave blank to insert, populate to update". If an update
template is genuinely needed, that is a separate artifact.

**Reference related records by human-friendly Name, not by Id.** Whoever fills the sheet has names, not
18-character keys.

- **Lookups and master-detail:** the column holds the related record's *name*, and the header gets a
  " Name" suffix (for example "Site Name", "Account Name") to signal that match-by-name is the
  mechanism.
- **Record Type:** use the record type *name*, not `RecordTypeId`, with a dropdown of active assignable
  names. Record type names are org-independent metadata, identical between sandbox and production, so
  source them from any org.
- If an Id genuinely must appear and it differs by org, source it from the org that will actually be
  loaded.

Two mechanical notes if you build the generator: filter the field list by what is on the object's
canonical Lightning record page and drop anything an approval or workflow auto-populates, and put
dropdown values on a hidden sheet so they can contain commas and exceed Excel's 255-character
inline-validation limit.
