#!/usr/bin/env python3
"""Convert plain text into a Jira ADF payload, so a description or comment keeps its structure.

Jira stores a description and a comment body as an ADF document. Send prose as a plain string and the
whole thing arrives as a SINGLE ADF text node: blank lines and "- " bullets survive only as literal
newline characters inside one paragraph, and the item renders as an unbroken blob under a real
person's name. Nothing signals the loss, because the flattened form is equally valid ADF, so confirm
by reading the stored ADF back rather than by the 204/201.

The `{"fields": ...}` wrapper this script emits is exactly the shape the REST endpoints take, so pass
its output to curl unmodified. Auth is a classic API token in ~/.netrc.

Blocks are separated by a blank line, and inside a block every run of lines starting with "- " or
"• " is its own bulletList, whether or not a blank line sets it apart: a header line directly over
two "- " lines gives a paragraph and then a bulletList, the same as with a blank line between them.
"• " counts so that a list drafted with that marker for a chat or email preview can be posted from
the same file unchanged; when only "- " counted, a list written with "• " posted as one paragraph of
literal bullets. Of the lines left, a run whose every line starts with a number and a dot or bracket
("1. ", "2) ") becomes an orderedList, and anything else becomes a paragraph with its lines joined by
spaces, which is what Jira wants anyway. A numbered run still needs the blank line before it: a
bullet marker is unambiguous and a number with a period is not (a year can open a sentence the same
way), so numbers are honored only when the whole run is numbered. The flip side is recorded rather
than guarded against: a line opening with a year and a period ("2026. A year of two halves.") reads
as a list starting at 2026, so recast the sentence if it ever matters. Paragraphs and lists are the
whole vocabulary on purpose: headings and panels are rarely worth the complexity in a ticket body,
and an inline image needs an `external` media node built by hand (qa-handoff shows one).

An orderedList carries attrs.order taken from the FIRST line's own number, so a numbered run split
across blocks continues rather than restarting. That matters because consecutive orderedList nodes
restart at 1 in Jira, which silently renumbers steps split by a callout, and because the numbers are
what a reader records results against. Write the numbers you want and they are honored: a block
starting "8." renders as 8.

Numbered text is why that branch exists rather than being a nicety. Before it, a numbered block fell
through to the paragraph branch and became ONE paragraph with the numbers as literal characters, the
same flattening this script exists to prevent, in a shape the docstring did not warn about.

Splitting bullet runs inside a block is the same lesson again. When a header line sat directly over
its bullets with no blank line between, the whole block used to become ONE paragraph carrying the
literal "- " markers, and only reading the stored ADF types back caught it.

Write an @-mention as @[Display Name]. The brackets are what make it parseable: a display name
contains spaces, so a bare "@Jordan Lee" gives nothing to mark where the name stops and the sentence
starts. Each name is resolved through /rest/api/3/user/search on the site named by --site (or the
JIRA_SITE environment variable), keeping only ACTIVE accounts whose accountType is "atlassian" and
whose displayName matches exactly, ignoring case. Both filters earn their place. On a site that also
runs Jira Service Management, people commonly have a non-assignable customer account ("qm:...")
beside their real one, and a mention carrying that id renders as nothing; and a user search returns
near-matches, so a query for one person's full name can also return a colleague who shares the
surname. Zero matches or more than one raises rather than falling back to plain text, because a
mention that quietly degrades notifies nobody and the stored ADF is the only place the difference
shows. Text with no @[...] in it never touches the network.

Usage:
    # description on a work item
    python jira-text-to-adf.py body.txt --field description > payload.json
    curl --netrc -X PUT https://your-site.atlassian.net/rest/api/3/issue/PROJ-510 -sS \
        -H 'Content-Type: application/json' --data @payload.json

    # a comment body (different endpoint, and the field is named "body")
    python jira-text-to-adf.py note.txt --field body > payload.json
    curl --netrc -X POST https://your-site.atlassian.net/rest/api/3/issue/PROJ-510/comment -sS \
        -H 'Content-Type: application/json' --data @payload.json

    # a comment that @-mentions somebody: write "@[Jordan Lee]" in note.txt and name the site
    python jira-text-to-adf.py note.txt --field body --site your-site.atlassian.net > payload.json

A PUT to the issue endpoint answers 204 with no body; a POST to the comment endpoint answers 201.
Confirm the structure landed by reading it back on v3 rather than trusting either code:
    curl -sS --netrc ".../rest/api/3/issue/PROJ-510?fields=description" \
        | jq '.fields.description.content | length'
"""

from __future__ import annotations

import argparse
import functools
import json
import netrc
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from itertools import groupby


# "@[Jordan Lee]" - the brackets are load-bearing, because a display name contains spaces and a bare
# "@Jordan Lee" gives no way to tell where the name stops and the sentence starts.
_MENTION = re.compile(r"@\[([^\]\n]+)\]")


class MentionError(Exception):
    """A name in @[...] could not be resolved to exactly one assignable account."""


def _site_host(site: str | None) -> str:
    """The Jira host for mentions: --site, else JIRA_SITE, with any scheme and slash stripped."""
    host = (site or os.environ.get("JIRA_SITE", "")).strip()
    host = re.sub(r"^https?://", "", host).rstrip("/")
    if not host:
        raise MentionError(
            "an @[...] mention needs a Jira site to resolve against: "
            "pass --site your-site.atlassian.net or set JIRA_SITE"
        )
    return host


def _jira_get(host: str, path: str) -> object:
    """GET a Jira REST path as the classic API token in ~/.netrc for machine `host`."""
    try:
        auth = netrc.netrc().authenticators(host)
    except (OSError, netrc.NetrcParseError) as exc:
        raise MentionError(f"could not read ~/.netrc for {host}: {exc}") from exc
    if not auth:
        raise MentionError(f"no ~/.netrc entry for machine {host}")
    login, _, password = auth
    token = b64encode(f"{login}:{password}".encode()).decode()
    req = urllib.request.Request(
        f"https://{host}{path}",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise MentionError(f"Jira returned {exc.code} for {path}") from exc
    except urllib.error.URLError as exc:
        raise MentionError(f"could not reach {host}: {exc.reason}") from exc


def resolve_mention(name: str, site: str | None = None) -> str:
    """Return the assignable accountId for a display name, or raise.

    On a site that also runs Jira Service Management, people commonly have a non-assignable
    CUSTOMER account (accountId "qm:...", accountType "customer") beside their real one, and a
    mention carrying the customer id renders as nothing. So keep only active "atlassian" accounts
    whose displayName is exactly the name asked for: a search by full name also returns colleagues
    who share the surname, so filtering on accountType alone is not enough. Raise on zero or more
    than one rather than picking, because a mention that quietly degrades to plain text is the
    failure this exists to prevent.
    """
    host = _site_host(site)
    query = urllib.parse.quote(name)
    users = _jira_get(host, f"/rest/api/3/user/search?query={query}")
    if not isinstance(users, list):
        raise MentionError(f"unexpected user-search response for {name!r}")
    hits = [
        u
        for u in users
        if u.get("accountType") == "atlassian"
        and u.get("active")
        and (u.get("displayName") or "").strip().casefold() == name.strip().casefold()
    ]
    if not hits:
        customer = [u for u in users if str(u.get("accountId", "")).startswith("qm:")]
        extra = " (only a non-assignable customer account was found)" if customer else ""
        raise MentionError(f"no assignable Jira account for @[{name}]{extra}")
    if len(hits) > 1:
        ids = ", ".join(u["accountId"] for u in hits)
        raise MentionError(f"@[{name}] is ambiguous: {len(hits)} accounts ({ids})")
    return hits[0]["accountId"]


def _inline_nodes(text: str, resolve) -> list[dict]:
    """Split a run of text into text nodes and mention nodes."""
    nodes: list[dict] = []
    pos = 0
    for m in _MENTION.finditer(text):
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos : m.start()]})
        name = m.group(1).strip()
        nodes.append(
            {"type": "mention", "attrs": {"id": resolve(name), "text": f"@{name}"}}
        )
        pos = m.end()
    if pos < len(text):
        nodes.append({"type": "text", "text": text[pos:]})
    return nodes or [{"type": "text", "text": text}]


def _paragraph(text: str, resolve=resolve_mention) -> dict:
    return {"type": "paragraph", "content": _inline_nodes(text, resolve)}


def _bullet_list(items: list[str], resolve=resolve_mention) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [_paragraph(i, resolve)]} for i in items
        ],
    }


# "1. ", "2) ", "10." - the marker a person actually types in a numbered list.
_ORDERED = re.compile(r"^(\d+)[.)]\s+(.*)$")


def _ordered_list(items: list[str], order: int, resolve=resolve_mention) -> dict:
    node = {
        "type": "orderedList",
        "content": [
            {"type": "listItem", "content": [_paragraph(i, resolve)]} for i in items
        ],
    }
    # Jira restarts every orderedList at 1 unless told otherwise, so always carry the start.
    node["attrs"] = {"order": order}
    return node


# Both markers are two characters, which is what the ln[2:] in _block_nodes strips.
_BULLETS = ("- ", "• ")


def _block_nodes(lines: list[str], resolve=resolve_mention) -> list[dict]:
    nodes: list[dict] = []
    for is_bullet, group in groupby(lines, key=lambda ln: ln.startswith(_BULLETS)):
        run = list(group)
        if is_bullet:
            nodes.append(_bullet_list([ln[2:] for ln in run], resolve))
            continue
        numbered = [_ORDERED.match(ln) for ln in run]
        if all(numbered):
            nodes.append(
                _ordered_list(
                    [m.group(2) for m in numbered],
                    int(numbered[0].group(1)),
                    resolve,
                )
            )
        else:
            nodes.append(_paragraph(" ".join(run), resolve))
    return nodes


def to_adf(text: str, resolve=resolve_mention) -> dict:
    """Turn plain text into an ADF doc of paragraphs, bullets, and numbered lists.

    Blank lines separate blocks, and inside a block every run of "- " or "• " lines is its own
    bulletList.
    """
    content: list[dict] = []
    for block in text.split("\n\n"):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        content.extend(_block_nodes(lines, resolve))
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
    ap.add_argument(
        "--site",
        help="Jira host that @[Display Name] mentions resolve against, such as "
        "your-site.atlassian.net (default: the JIRA_SITE environment variable); "
        "needed only when the text contains a mention",
    )
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as fh:
        doc = to_adf(fh.read(), functools.partial(resolve_mention, site=args.site))

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
