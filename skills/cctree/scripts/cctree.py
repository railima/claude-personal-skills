#!/usr/bin/env python3
"""Standalone, dependency-free helper for the cctree skill.

Mirrors the on-disk layout of the cctree npm package (~/.cctree) so the two are
interoperable, but needs no Node, no MCP server, and no API key. It handles the
deterministic, stateful parts of the workflow (creating trees, registering
sessions, storing structured summaries, rebuilding accumulated context). The
judgement parts (deciding when to commit, writing a good summary, synthesising
diagrams) are left to the agent that reads SKILL.md.

Usage:
  cctree.py init   <name> [--context f1 f2 ...]
  cctree.py branch <name> [--tags a,b,c] [--tree <t>]
  cctree.py commit <child> (--file <path> | --stdin) [--tree <t>]
  cctree.py recall <child> [--tree <t>]
  cctree.py context [--raw] [--tree <t>]
  cctree.py list   [--all] [--tag <t>] [--search <q>]
  cctree.py find   <query>
  cctree.py status
  cctree.py use    <tree>
  cctree.py abandon <child> [--delete] [--tree <t>]
  cctree.py report  <tree>
  cctree.py mermaid [--tree <t>]
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(os.environ.get("CCTREE_HOME", Path.home() / ".cctree"))
TREES = BASE / "trees"
ACTIVE_TREE = BASE / "active-tree"
ACTIVE_SESSION = BASE / "active-session.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def to_slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = re.sub(r"^-|-$", "", s)
    return s


def assert_valid_slug(slug: str, label: str) -> None:
    if not slug or not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        die(f'Invalid {label}: "{slug}". Must contain at least one alphanumeric character.')


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def tree_dir(slug: str) -> Path:
    return TREES / slug


def tree_json(slug: str) -> Path:
    return TREES / slug / "tree.json"


def context_path(slug: str) -> Path:
    return TREES / slug / "context.md"


def initial_context_dir(slug: str) -> Path:
    return TREES / slug / "initial-context"


def children_dir(slug: str) -> Path:
    return TREES / slug / "children"


def child_summary_path(tree_slug: str, child_slug: str) -> Path:
    return TREES / tree_slug / "children" / f"{child_slug}.md"


def load_tree(slug: str) -> dict:
    p = tree_json(slug)
    if not p.exists():
        die(f'Tree "{slug}" not found. Run "init" to create one.')
    return json.loads(p.read_text(encoding="utf-8"))


def save_tree(cfg: dict) -> None:
    tree_json(cfg["slug"]).write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def list_trees() -> list:
    TREES.mkdir(parents=True, exist_ok=True)
    out = []
    for entry in sorted(TREES.iterdir()):
        if entry.is_dir() and (entry / "tree.json").exists():
            try:
                out.append(json.loads((entry / "tree.json").read_text(encoding="utf-8")))
            except Exception:
                pass
    out.sort(key=lambda t: t.get("created_at", ""))
    return out


def resolve_tree(name_or_slug: str) -> dict:
    trees = list_trees()
    slug = to_slug(name_or_slug)
    lower = name_or_slug.lower()
    for t in trees:
        if t["slug"] in (slug, lower) or t["name"].lower() == lower:
            return t
    available = (
        "\nAvailable trees:\n" + "\n".join(f'  - {t["name"]} ({t["slug"]})' for t in trees)
        if trees
        else ""
    )
    die(f'Tree "{name_or_slug}" not found.{available}')


def get_active_tree_slug() -> str | None:
    try:
        s = ACTIVE_TREE.read_text(encoding="utf-8").strip()
        return s or None
    except OSError:
        return None


def set_active_tree(slug: str) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    ACTIVE_TREE.write_text(slug, encoding="utf-8")


def write_active_session(tree: str, child: str) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    ACTIVE_SESSION.write_text(json.dumps({"tree": tree, "child": child}, indent=2), encoding="utf-8")


def read_active_session() -> dict | None:
    try:
        return json.loads(ACTIVE_SESSION.read_text(encoding="utf-8"))
    except OSError:
        return None


def target_tree(explicit: str | None) -> dict:
    """Resolve a tree from --tree, else the active tree."""
    if explicit:
        return resolve_tree(explicit)
    slug = get_active_tree_slug()
    if not slug:
        die('No active tree. Run "init" or "use <name>" first.')
    return load_tree(slug)


def find_child(cfg: dict, name_or_slug: str) -> dict | None:
    lower = name_or_slug.lower()
    for c in cfg["children"]:
        if c["slug"] == lower or c["name"].lower() == lower:
            return c
    return None


def fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %-d, %Y")
    except ValueError:
        return ""


# ---------------------------------------------------------------------------
# summary parsing (ported from src/lib/summary-sections.ts)
# ---------------------------------------------------------------------------
MATCHERS = [
    ("tldr", "text", [r"^##\s+tl;?\s*dr\s*$", r"^##\s+resumo\s*$", r"^##\s+sum[áa]rio\s*$"]),
    ("decisions", "bullet", [r"^##\s+decisions\s*$", r"^##\s+decis[õo]es\s*$"]),
    (
        "artifacts",
        "bullet",
        [
            r"^##\s+artifacts\s+created\s*$",
            r"^##\s+artifacts\s*$",
            r"^##\s+artefatos\s+criados\s*$",
            r"^##\s+artefatos\s*$",
        ],
    ),
    (
        "open_questions",
        "bullet",
        [r"^##\s+open\s+questions\s*$", r"^##\s+perguntas\s+abertas\s*$", r"^##\s+quest[õo]es\s+abertas\s*$"],
    ),
    ("next_steps", "bullet", [r"^##\s+next\s+steps\s*$", r"^##\s+pr[óo]ximos\s+passos\s*$"]),
    ("details", "text", [r"^##\s+details\s*$", r"^##\s+detalhes\s*$"]),
]


def _match_section(line: str):
    for key, kind, patterns in MATCHERS:
        for pat in patterns:
            if re.match(pat, line, re.IGNORECASE):
                return key, kind
    return None


def parse_summary(summary: str) -> dict:
    sections = {
        "tldr": "",
        "decisions": [],
        "artifacts": [],
        "open_questions": [],
        "next_steps": [],
        "details": "",
    }
    cur_key = None
    cur_kind = None
    bullet = None
    text_buf: list[str] = []

    def flush_bullet():
        nonlocal bullet
        if bullet is not None and cur_key is not None and cur_kind == "bullet":
            t = bullet.strip()
            if t:
                sections[cur_key].append(t)
        bullet = None

    def flush_text():
        nonlocal text_buf
        if text_buf and cur_key is not None and cur_kind == "text":
            joined = "\n".join(text_buf).strip()
            if joined:
                sections[cur_key] = joined
        text_buf = []

    def flush():
        flush_bullet()
        flush_text()

    for line in summary.splitlines():
        matched = _match_section(line)
        if matched:
            flush()
            cur_key, cur_kind = matched
            continue
        if cur_key is None:
            continue
        if re.match(r"^##\s+", line):
            flush()
            cur_key = cur_kind = None
            continue
        if cur_kind == "text":
            text_buf.append(line)
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_bullet()
            bullet = re.sub(r"^\s*[-*]\s+", "", line).strip()
        elif bullet is not None and line.strip():
            bullet += " " + line.strip()
        elif bullet is not None and not line.strip():
            flush_bullet()
    flush()
    return sections


def render_injectable(sections: dict) -> str:
    parts = []
    if sections["tldr"]:
        parts += ["## TL;DR", sections["tldr"], ""]
    if sections["decisions"]:
        parts.append("## Decisions")
        parts += [f"- {d}" for d in sections["decisions"]]
        parts.append("")
    if sections["artifacts"]:
        parts.append("## Artifacts")
        parts += [f"- {a}" for a in sections["artifacts"]]
        parts.append("")
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# context rebuild (ported from src/lib/context-builder.ts)
# ---------------------------------------------------------------------------
def rebuild_context(slug: str) -> str:
    cfg = load_tree(slug)
    sections = [f'# Context: {cfg["name"]}', ""]

    icdir = initial_context_dir(slug)
    if icdir.exists():
        files = sorted(f.name for f in icdir.iterdir() if f.is_file())
        if files:
            sections += ["## Initial Context", ""]
            for f in files:
                sections += [f"### {f}", "", (icdir / f).read_text(encoding="utf-8").strip(), ""]

    committed = [c for c in cfg["children"] if c["status"] == "committed" and c.get("committed_at")]
    committed.sort(key=lambda c: c.get("committed_at", ""))
    for child in committed:
        sp = child_summary_path(slug, child["slug"])
        if not sp.exists():
            continue
        injectable = render_injectable(parse_summary(sp.read_text(encoding="utf-8")))
        if not injectable:
            injectable = sp.read_text(encoding="utf-8").strip()
        if not injectable:
            continue
        date = fmt_date(child.get("committed_at"))
        sections += [f'## Session: {child["name"]}' + (f" ({date})" if date else ""), "", injectable, ""]

    content = "\n".join(sections).strip() + "\n"
    context_path(slug).write_text(content, encoding="utf-8")
    return content


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_init(args):
    slug = to_slug(args.name)
    assert_valid_slug(slug, "tree name")
    if tree_json(slug).exists():
        die(f'Tree "{args.name}" already exists.')

    initial_context_dir(slug).mkdir(parents=True, exist_ok=True)
    children_dir(slug).mkdir(parents=True, exist_ok=True)

    copied = []
    for f in args.context or []:
        src = Path(f).expanduser().resolve()
        if not src.exists():
            die(f'Context file "{f}" does not exist.')
        dest = initial_context_dir(slug) / src.name
        shutil.copy2(src, dest)
        copied.append(src.name)

    cfg = {
        "name": args.name,
        "slug": slug,
        "created_at": now_iso(),
        "cwd": os.getcwd(),
        "initial_context_files": copied,
        "children": [],
    }
    save_tree(cfg)
    rebuild_context(slug)
    set_active_tree(slug)

    print(f'Created tree "{args.name}" ({slug}).')
    if copied:
        print(f'Initial context: {", ".join(copied)}')
    print(f"Active tree set to {slug}.")


def cmd_branch(args):
    cfg = target_tree(args.tree)
    slug = to_slug(args.name)
    assert_valid_slug(slug, "session name")
    if find_child(cfg, args.name) or any(c["slug"] == slug for c in cfg["children"]):
        die(f'Child session "{args.name}" already exists in tree "{cfg["name"]}".')

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    tags = [t for t in tags if t]
    child = {
        "name": args.name,
        "slug": slug,
        "status": "active",
        "claude_session_name": slug,
        "created_at": now_iso(),
    }
    if tags:
        child["tags"] = tags
    cfg["children"].append(child)
    save_tree(cfg)
    write_active_session(cfg["slug"], slug)
    set_active_tree(cfg["slug"])

    print(f'Registered session "{args.name}" ({slug}) in tree "{cfg["name"]}".')
    if tags:
        print(f'Tags: {", ".join(tags)}')
    committed = sum(1 for c in cfg["children"] if c["status"] == "committed")
    print(f"Accumulated context covers {committed} committed sibling(s).")
    print("Next: load it into this conversation with `context`.")


def _read_summary(args) -> str:
    if args.stdin:
        return sys.stdin.read()
    if args.file:
        p = Path(args.file).expanduser()
        if not p.exists():
            die(f'Summary file "{args.file}" not found.')
        return p.read_text(encoding="utf-8")
    die("commit needs --file <path> or --stdin")


def cmd_commit(args):
    cfg = target_tree(args.tree)
    child = find_child(cfg, args.child)
    if not child:
        die(f'Child session "{args.child}" not found in tree "{cfg["name"]}".')

    content = _read_summary(args).strip()
    if not content:
        die("refusing to commit an empty summary.")
    parsed = parse_summary(content)
    if not parsed["tldr"] and not parsed["decisions"]:
        print(
            "warning: summary has no recognised ## TL;DR or ## Decisions section; "
            "siblings will inherit the raw text. See SKILL.md for the expected structure.",
            file=sys.stderr,
        )

    children_dir(cfg["slug"]).mkdir(parents=True, exist_ok=True)
    child_summary_path(cfg["slug"], child["slug"]).write_text(content + "\n", encoding="utf-8")
    child["status"] = "committed"
    child["committed_at"] = now_iso()
    save_tree(cfg)
    ctx = rebuild_context(cfg["slug"])

    committed = sum(1 for c in cfg["children"] if c["status"] == "committed")
    size_kb = len(ctx.encode("utf-8")) / 1024
    print(f'Committed summary for "{child["name"]}" to tree "{cfg["name"]}".')
    print(f"Accumulated context: {size_kb:.1f} KB ({committed} session(s) committed).")


def cmd_recall(args):
    cfg = target_tree(args.tree)
    child = find_child(cfg, args.child)
    if not child:
        die(f'Child session "{args.child}" not found in tree "{cfg["name"]}".')
    sp = child_summary_path(cfg["slug"], child["slug"])
    if not sp.exists():
        die(f'No summary found for "{child["name"]}". It may not have been committed yet.')
    print(sp.read_text(encoding="utf-8"))


def cmd_context(args):
    cfg = target_tree(args.tree)
    print(rebuild_context(cfg["slug"]), end="")


def _matches_query(child: dict, cfg: dict, q: str) -> bool:
    q = q.lower()
    hay = [child["name"], child["slug"], cfg["name"]]
    hay += child.get("tags", [])
    sp = child_summary_path(cfg["slug"], child["slug"])
    if sp.exists():
        parsed = parse_summary(sp.read_text(encoding="utf-8"))
        hay.append(parsed["tldr"])
        hay += parsed["decisions"]
        hay += parsed["artifacts"]
    return any(q in str(h).lower() for h in hay)


STATUS_MARK = {"committed": "[x]", "active": "[ ]", "abandoned": "[~]"}


def _print_tree(cfg: dict, tag=None, search=None):
    print(f'{cfg["name"]} ({cfg["slug"]})')
    children = cfg["children"]
    if tag:
        children = [c for c in children if tag in c.get("tags", [])]
    if search:
        children = [c for c in children if _matches_query(c, cfg, search)]
    if not children:
        print("  (no matching sessions)")
        return
    for c in children:
        mark = STATUS_MARK.get(c["status"], "[ ]")
        tags = f'  #{",#".join(c["tags"])}' if c.get("tags") else ""
        date = fmt_date(c.get("committed_at"))
        date = f"  · {date}" if date else ""
        print(f'  {mark} {c["name"]} ({c["slug"]}){tags}{date}')


def cmd_list(args):
    if args.all:
        trees = list_trees()
        if not trees:
            print("No trees yet. Run `init <name>`.")
            return
        for i, t in enumerate(trees):
            if i:
                print()
            _print_tree(t, args.tag, args.search)
    else:
        cfg = target_tree(None)
        _print_tree(cfg, args.tag, args.search)


def cmd_find(args):
    trees = list_trees()
    hits = 0
    for cfg in trees:
        matching = [c for c in cfg["children"] if _matches_query(c, cfg, args.query)]
        if matching:
            print(f'{cfg["name"]} ({cfg["slug"]})')
            for c in matching:
                mark = STATUS_MARK.get(c["status"], "[ ]")
                print(f'  {mark} {c["name"]} ({c["slug"]})')
            hits += len(matching)
    if not hits:
        print(f'No sessions match "{args.query}".')


def cmd_status(args):
    slug = get_active_tree_slug()
    if not slug:
        print("No active tree. Run `init <name>` or `use <name>`.")
        return
    cfg = load_tree(slug)
    sess = read_active_session()
    total = len(cfg["children"])
    committed = sum(1 for c in cfg["children"] if c["status"] == "committed")
    active = sum(1 for c in cfg["children"] if c["status"] == "active")
    print(f'Active tree: {cfg["name"]} ({cfg["slug"]})')
    if sess and sess.get("tree") == slug and sess.get("child"):
        print(f'Active session: {sess["child"]}')
    print(f"Sessions: {total} total · {committed} committed · {active} active")


def cmd_use(args):
    cfg = resolve_tree(args.tree)
    set_active_tree(cfg["slug"])
    print(f'Active tree set to {cfg["name"]} ({cfg["slug"]}).')


def cmd_abandon(args):
    cfg = target_tree(args.tree)
    child = find_child(cfg, args.child)
    if not child:
        die(f'Child session "{args.child}" not found in tree "{cfg["name"]}".')
    if args.delete:
        cfg["children"] = [c for c in cfg["children"] if c["slug"] != child["slug"]]
        child_summary_path(cfg["slug"], child["slug"]).unlink(missing_ok=True)
        save_tree(cfg)
        rebuild_context(cfg["slug"])
        sess = read_active_session()
        if sess and sess.get("tree") == cfg["slug"] and sess.get("child") == child["slug"]:
            ACTIVE_SESSION.unlink(missing_ok=True)
        print(f'Deleted session "{child["name"]}" from tree "{cfg["name"]}".')
    else:
        child["status"] = "abandoned"
        save_tree(cfg)
        rebuild_context(cfg["slug"])
        print(f'Marked session "{child["name"]}" as abandoned.')


def cmd_report(args):
    cfg = resolve_tree(args.tree)
    committed = [c for c in cfg["children"] if c["status"] == "committed"]
    committed.sort(key=lambda c: c.get("committed_at", ""))

    out = [f'# Progress Report — {cfg["name"]}', "", f"_Generated {fmt_date(now_iso())}_", ""]
    out += [
        f"**{len(cfg['children'])}** sessions · "
        f"**{len(committed)}** committed · "
        f"**{sum(1 for c in cfg['children'] if c['status'] == 'active')}** active",
        "",
    ]

    all_decisions, all_questions, all_next = [], [], []
    for c in committed:
        sp = child_summary_path(cfg["slug"], c["slug"])
        if not sp.exists():
            continue
        p = parse_summary(sp.read_text(encoding="utf-8"))
        all_decisions += [(c["name"], d) for d in p["decisions"]]
        all_questions += [(c["name"], q) for q in p["open_questions"]]
        all_next += [(c["name"], n) for n in p["next_steps"]]

    if all_decisions:
        out += ["## Decisions", ""]
        out += [f"- {d} _({src})_" for src, d in all_decisions]
        out.append("")
    if all_questions:
        out += ["## Open Questions", ""]
        out += [f"- {q} _({src})_" for src, q in all_questions]
        out.append("")
    if all_next:
        out += ["## Next Steps", ""]
        out += [f"- {n} _({src})_" for src, n in all_next]
        out.append("")

    out += ["## Timeline", ""]
    for c in committed:
        out.append(f'- **{fmt_date(c.get("committed_at"))}** — {c["name"]}')
    if not committed:
        out.append("- (nothing committed yet)")
    out.append("")

    out += ["## Structure", "", "```"]
    out.append(f'{cfg["name"]}')
    for c in cfg["children"]:
        out.append(f'  {STATUS_MARK.get(c["status"], "[ ]")} {c["name"]}')
    out.append("```")

    print("\n".join(out))


def cmd_mermaid(args):
    trees = [resolve_tree(args.tree)] if args.tree else list_trees()
    if not trees:
        die("no trees to render.")
    lines = ["graph TD"]
    for cfg in trees:
        tslug = cfg["slug"]
        lines.append(f'  {tslug}["{cfg["name"]}"]')
        for c in cfg["children"]:
            cid = f"{tslug}__{c['slug']}"
            shape_l, shape_r = ("([", "])") if c["status"] == "committed" else ("[", "]")
            label = c["name"] + ("" if c["status"] == "active" else f" ({c['status']})")
            lines.append(f'  {cid}{shape_l}"{label}"{shape_r}')
            lines.append(f"  {tslug} --> {cid}")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(prog="cctree", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="create a new session tree")
    sp.add_argument("name")
    sp.add_argument("--context", nargs="*", help="initial context files")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("branch", help="register a child session")
    sp.add_argument("name")
    sp.add_argument("--tags", help="comma-separated tags")
    sp.add_argument("--tree")
    sp.set_defaults(func=cmd_branch)

    sp = sub.add_parser("commit", help="store a structured summary for a session")
    sp.add_argument("child")
    sp.add_argument("--file", help="path to the summary markdown")
    sp.add_argument("--stdin", action="store_true", help="read the summary from stdin")
    sp.add_argument("--tree")
    sp.set_defaults(func=cmd_commit)

    sp = sub.add_parser("recall", help="print a sibling's full committed summary")
    sp.add_argument("child")
    sp.add_argument("--tree")
    sp.set_defaults(func=cmd_recall)

    sp = sub.add_parser("context", help="print the accumulated context for the tree")
    sp.add_argument("--raw", action="store_true")
    sp.add_argument("--tree")
    sp.set_defaults(func=cmd_context)

    sp = sub.add_parser("list", help="show the session tree")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--tag")
    sp.add_argument("--search")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("find", help="search across all trees")
    sp.add_argument("query")
    sp.set_defaults(func=cmd_find)

    sp = sub.add_parser("status", help="show the active tree")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("use", help="switch the active tree")
    sp.add_argument("tree")
    sp.set_defaults(func=cmd_use)

    sp = sub.add_parser("abandon", help="abandon or delete a session")
    sp.add_argument("child")
    sp.add_argument("--delete", action="store_true")
    sp.add_argument("--tree")
    sp.set_defaults(func=cmd_abandon)

    sp = sub.add_parser("report", help="generate a markdown progress report")
    sp.add_argument("tree")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("mermaid", help="render the trees as a Mermaid diagram")
    sp.add_argument("--tree")
    sp.set_defaults(func=cmd_mermaid)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
