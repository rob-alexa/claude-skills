#!/usr/bin/env python3
"""Convert plain text into a Jira ADF payload, so a description or comment keeps its structure.

Jira stores a description and a comment body as an ADF document. Send prose as a plain string and the
whole thing arrives as a SINGLE ADF text node: blank lines and "- " bullets survive only as literal
newline characters inside one paragraph, and the item renders as an unbroken blob under a real
person's name. Nothing signals the loss, because the flattened form is equally valid ADF, so confirm
by reading the stored ADF back rather than by the 204/201.

The `{"fields": ...}` wrapper this script emits is exactly the shape the REST endpoints take, so pass
its output to curl unmodified. Auth is a classic API token in ~/.netrc.

Blocks are separated by a blank line. A block whose every line starts with "- " becomes a bulletList,
a block whose every line starts with a number and a dot or bracket ("1. ", "2) ") becomes an
orderedList, and anything else becomes a paragraph with its lines joined by spaces, which is what
Jira wants anyway. Paragraphs and lists are the whole vocabulary on purpose: headings and panels are
rarely worth the complexity in a ticket body, and an inline image is not possible over REST at all.

An orderedList carries attrs.order taken from the FIRST line's own number, so a numbered run split
across blocks continues rather than restarting. That matters because consecutive orderedList nodes
restart at 1 in Jira, which silently renumbers steps split by a callout, and because the numbers are
what a reader records results against. Write the numbers you want and they are honored: a block
starting "8." renders as 8.

Numbered text is why that branch exists rather than being a nicety. Before it, a numbered block fell
through to the paragraph branch and became ONE paragraph with the numbers as literal characters, the
same flattening this script exists to prevent, in a shape the docstring did not warn about.

Usage:
    # description on a work item
    python jira-text-to-adf.py body.txt --field description > payload.json
    curl -sS --netrc -X PUT -H 'Content-Type: application/json' --data @payload.json \
        "https://your-site.atlassian.net/rest/api/3/issue/PROJ-510"

    # a comment body (different endpoint, and the field is named "body")
    python jira-text-to-adf.py note.txt --field body > payload.json
    curl -sS --netrc -X POST -H 'Content-Type: application/json' --data @payload.json \
        "https://your-site.atlassian.net/rest/api/3/issue/PROJ-510/comment"

A PUT to the issue endpoint answers 204 with no body; a POST to the comment endpoint answers 201.
Confirm the structure landed by reading it back rather than trusting either code:
    curl -sS --netrc ".../issue/PROJ-510?fields=description" | jq '.fields.description.content | length'
"""

from __future__ import annotations

import argparse
import json
import re
import sys


def _paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _bullet_list(items: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [{"type": "listItem", "content": [_paragraph(i)]} for i in items],
    }


# "1. ", "2) ", "10." - the marker a person actually types in a numbered list.
_ORDERED = re.compile(r"^(\d+)[.)]\s+(.*)$")


def _ordered_list(items: list[str], order: int) -> dict:
    node = {
        "type": "orderedList",
        "content": [{"type": "listItem", "content": [_paragraph(i)]} for i in items],
    }
    # Jira restarts every orderedList at 1 unless told otherwise, so always carry the start.
    node["attrs"] = {"order": order}
    return node


def to_adf(text: str) -> dict:
    """Turn blank-line-separated plain text into an ADF doc of paragraphs, bullets, and numbered lists."""
    content: list[dict] = []
    for block in text.split("\n\n"):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        numbered = [_ORDERED.match(ln) for ln in lines]
        if all(ln.startswith("- ") for ln in lines):
            content.append(_bullet_list([ln[2:] for ln in lines]))
        elif all(numbered):
            content.append(
                _ordered_list(
                    [m.group(2) for m in numbered],
                    int(numbered[0].group(1)),
                )
            )
        else:
            content.append(_paragraph(" ".join(lines)))
    if not content:
        raise ValueError("no content: the input file is empty or only whitespace")
    return {"type": "doc", "version": 1, "content": content}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", help="plain-text file to convert")
    ap.add_argument(
        "--field",
        default="description",
        help='ADF target: "description" wraps in {"fields": {...}} for the issue endpoint, '
        '"body" wraps in {"body": ...} for the comment endpoint (default: description)',
    )
    ap.add_argument(
        "--bare",
        action="store_true",
        help="emit just the ADF document, unwrapped, for building a larger payload yourself",
    )
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as fh:
        doc = to_adf(fh.read())

    if args.bare:
        payload: dict = doc
    elif args.field == "body":
        payload = {"body": doc}
    else:
        payload = {"fields": {args.field: doc}}

    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    types = ", ".join(b["type"] for b in doc["content"])
    print(f"{len(doc['content'])} block(s): {types}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
