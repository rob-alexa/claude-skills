---
name: stakeholder-questionnaire
description: "Getting answers out of a colleague who holds knowledge you do not. TRIGGER when: a decision needs input from Legal, a project manager, or a business owner, a story stalls on something only a stakeholder can answer, several open questions are piling up for one person, or a meeting needs an agenda of questions. Interview about the send, not the subject."
metadata:
  version: "1.1"
  license: MIT
  adapted_from: "https://github.com/mattpocock/skills (to-questionnaire) - MIT, Copyright (c) 2026 Matt Pocock"
---

# stakeholder-questionnaire

Turn questions you cannot answer into a **questionnaire**: one document a named colleague fills in
async, or that you both work through in a meeting.

Adapted from Matt Pocock's `to-questionnaire` skill (https://github.com/mattpocock/skills, MIT), with
the output moved from a bare Markdown file in the working directory to a formatted document, since a
raw `.md` is not something a Legal reviewer or a business owner is going to open and fill in.

## Grill the send, not the subject

Interview whoever is directing the work about the **send**, which they can always answer: who it goes
to, and what they need back. The questions in the document then target the **gap** between what the
recipient knows and what your side does not.

Asking them about the subject instead is how a questionnaire ends up asking its own author's questions
back at them.

## Two exchanges, then write it

1. **Who is it going to?** Their role, what they own, and what they know that you do not. This sets
   the tone and how much context the document has to carry. A Legal reviewer and a project manager
   need different framings of the same question.
2. **What do you need back?** The specific decisions or facts you cannot resolve alone. Done when you
   have a concrete list of what you must walk away able to decide.

Then write it, and cover every item from the second exchange.

## Never spend a question on something you can look up

The recipient gets one pass, so every question the system, the repository, or the tracker could have
answered is a question you did not get to ask. Settle the facts yourself first and put only genuine
gaps in the document.

**Ask nothing that can only be answered in a tool the recipient does not use.** A question mentioning
a branch, a PR, a source file, or a merge conflict is not a question to someone who has never used
git, it is a description of somewhere they cannot go. Every question has to be answerable from the
application's own admin screens, from a record page, or from what they know about the business. Where
the answer really does live in source, find it yourself and put the finding in the document as
context.

## The document

Order questions most-important-first, since an async send may only get one pass, and group them under
headings by theme once there are more than a handful. One idea per question, never compound, with an
answer stub directly beneath it, and a short line on why it matters only where the question could be
misread or invite a throwaway answer.

Open with:

- the purpose and the decision riding on it,
- one paragraph of context for a recipient who was not in your head,
- how to answer: an explicit deadline date, the rough effort, and that partial answers and "I don't
  know" are useful.

Close with a catch-all asking what you should have asked.

Produce it in a format the recipient will actually open, with a lowercase kebab-case filename, since
the filename becomes the document's visible title once it is shared.

## When the recipient has to type into it

**A formatted HTML document has nowhere to type, and a plain PDF is read-only, so a questionnaire
built for reading cannot be filled in.** That is a gap in this skill's own premise, not an edge case:
in the case behind this section, the first response to a finished HTML questionnaire was a request
for a writeable version. Keep a read-only document as the default, since that is what gets read; this
is the narrow case where a fillable one earns its place.

**Do not attach the HTML.** It is the right format for reading and for pasting into a rich-text
field, and the wrong one to attach anywhere: nothing renders a downloaded `.html` in place, so the
recipient is opening a file instead of looking at a document. That holds whether or not the
questionnaire needs to be fillable.

**Then decide between a fillable PDF and a Word document, and say which you picked and why.** A
**fillable PDF** keeps the styling exactly and opens the same way for everyone, at the cost of the
recipient's viewer having to save form data (Chrome, Edge, and Acrobat Reader all do). A **Word
document** is lower friction in an Office shop and easier to edit freely, at the cost of the styling,
since Word ignores CSS. Neither is obviously right, so offer the choice instead of assuming; the
first time this came up, the answer was the PDF.

**For the PDF route, give each answer stub a bordered box and keep it with its label.** The
`break-inside: avoid` is load-bearing: with the label and the box as separate blocks, a page break
strands the box alone on the next page with nothing saying what it is for. If you build from Markdown
with pandoc, keep the snippet on one unbroken line: pandoc ends a raw HTML block at any blank line and
wraps what follows in `<p>` tags.

```html
<div style="page-break-inside:avoid;break-inside:avoid;margin:10px 0 6px 0;"><p style="margin:0 0 6px 0;"><strong>Answer:</strong></p><div class="answerbox" style="min-height:92px;border:1px solid #c8c8c8;border-radius:3px;"></div></div>
```

Then add one multiline text field over each box. Two traps, both silent:

- **pypdf's `merge_page` drops the form.** It carries content streams but not widget annotations or
  the catalog's `/AcroForm`, so merging a field overlay into the content writes a valid PDF that
  opens fine and holds **zero** fields, with no error. Clone the overlay as the base and merge the
  content in underneath it; widgets render on top of page content either way. Then re-read the written
  file and count its fields, since nothing else will tell you.
- **A CSS box with rounded corners renders as a curve, not a rectangle.** Looking for the boxes in
  pdfplumber's `page.rects` found three where there were eight, with wrong coordinates; they are in
  `page.curves`.

Cross-check the boxes you find against the count of "Answer" labels, and refuse instead of guessing
when the two disagree, since a field placed over the wording is worse than no field.

**Attach only the format you are asking them to use.** Attaching two copies reads as a question about
which one to open. And tell them to download it before typing: whether Jira renders a PDF in place is
not established (its attachment API exposes no thumbnail for one), and downloading works either way.

## Write it for the person, not for the repo

- **No em dashes**, since this is addressed to another person and they render badly in most of the
  places it will be pasted.
- **Plain, calm language and a measured tone.** Prefer "I can" or "could" over "I'll" or "will" before
  anything is agreed, and hedge an unverified inference as one.
- **Do not presume the recipient's workflow.** Neutral phrasing when you are inferring what they do,
  and name each object and field by the label on their own screen rather than the API name.

## Drafting it is not sending it

Show the draft and stop. Approval of the content is not approval to send, and a questionnaire reaches
a real person under your name, so the send needs its own go-ahead. That covers posting it to the
tracker, attaching it to a work item, and pasting it into chat or an email.

Related: use `design-grilling` when the decisions are yours to settle rather than someone else's to
answer, and record what comes back wherever the implementation plan lives.
