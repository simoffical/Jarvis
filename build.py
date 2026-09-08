#!/usr/bin/env python3
"""Scan a folder of markdown notes and build viewer/graph-data.js for the
3D knowledge galaxy viewer.

Usage:
    python3 build.py [notes_dir]

Standard library only - no dependencies.
"""

import json
import os
import re
import sys

EXCERPT_LEN = 700

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
MD_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
CODE_FENCE_RE = re.compile(r"^[ \t]*```.*?$", re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
LIST_MARKER_RE = re.compile(r"^[ \t]*[-*+][ \t]+", re.MULTILINE)
BLOCKQUOTE_RE = re.compile(r"^[ \t]*>[ \t]?", re.MULTILINE)
HRULE_RE = re.compile(r"^[ \t]*(-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
EMPHASIS_RE = re.compile(r"(\*\*\*|\*\*|\*|___|__|_|~~)(\S.*?\S|\S)\1")


def find_markdown_files(root):
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.lower().endswith(".md"):
                paths.append(os.path.join(dirpath, name))
    paths.sort()
    return paths


def title_from_filename(path):
    base = os.path.basename(path)
    return re.sub(r"\.md$", "", base, flags=re.IGNORECASE)


def group_from_path(path, root):
    rel = os.path.relpath(path, root)
    folder = os.path.dirname(rel)
    if not folder or folder == ".":
        return "notes"
    return folder.split(os.sep)[0]


def clean_excerpt(text):
    text = FRONTMATTER_RE.sub("", text, count=1)
    text = CODE_FENCE_RE.sub("", text)
    text = MD_HEADING_RE.sub(lambda m: m.group(1), text)
    text = WIKILINK_RE.sub(lambda m: m.group(1), text)
    text = IMAGE_RE.sub(lambda m: m.group(1), text)
    text = LINK_RE.sub(lambda m: m.group(1), text)
    text = INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    text = HRULE_RE.sub("", text)
    text = LIST_MARKER_RE.sub("", text)
    text = BLOCKQUOTE_RE.sub("", text)
    for _ in range(2):
        text = EMPHASIS_RE.sub(lambda m: m.group(2), text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()

    if len(text) <= EXCERPT_LEN:
        return text
    cut = text[:EXCERPT_LEN]
    last_space = cut.rfind(" ")
    if last_space > EXCERPT_LEN * 0.6:
        cut = cut[:last_space]
    return cut.rstrip() + "..."


def build_graph(root):
    paths = find_markdown_files(root)

    nodes = []
    title_to_id = {}

    for path in paths:
        title = title_from_filename(path)
        group = group_from_path(path, root)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            raw = ""

        node_id = len(nodes)
        nodes.append(
            {
                "id": node_id,
                "label": title,
                "group": group,
                "excerpt": clean_excerpt(raw),
                "path": os.path.relpath(path, root),
                "raw": raw,
            }
        )
        title_to_id[title.strip().lower()] = node_id

    links = []
    seen_pairs = set()

    def add_link(a, b):
        if a == b:
            return
        key = (a, b) if a < b else (b, a)
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        links.append({"source": key[0], "target": key[1]})

    for node in nodes:
        raw = node["raw"]
        source_id = node["id"]

        for match in WIKILINK_RE.finditer(raw):
            target_title = match.group(1).strip().lower()
            target_id = title_to_id.get(target_title)
            if target_id is not None:
                add_link(source_id, target_id)

        lowered_raw = raw.lower()
        for other in nodes:
            if other["id"] == source_id:
                continue
            other_title = other["label"].strip().lower()
            if not other_title:
                continue
            pattern = r"\b" + re.escape(other_title) + r"\b"
            if re.search(pattern, lowered_raw):
                add_link(source_id, other["id"])

    for node in nodes:
        del node["raw"]

    return {"nodes": nodes, "links": links}


def main():
    notes_dir = sys.argv[1] if len(sys.argv) > 1 else "notes"
    notes_dir = os.path.abspath(notes_dir)

    if not os.path.isdir(notes_dir):
        print(f"Notes directory not found: {notes_dir}", file=sys.stderr)
        sys.exit(1)

    graph = build_graph(notes_dir)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    viewer_dir = os.path.join(script_dir, "viewer")
    os.makedirs(viewer_dir, exist_ok=True)
    out_path = os.path.join(viewer_dir, "graph-data.js")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const GRAPH = ")
        json.dump(graph, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(
        f"Scanned {len(graph['nodes'])} notes, found {len(graph['links'])} "
        f"links. Wrote {out_path}"
    )


if __name__ == "__main__":
    main()
