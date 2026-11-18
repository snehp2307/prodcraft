#!/usr/bin/env python3
"""Read-only repository inventory for a production review.

Walks a repository and reports what a reviewer needs to plan the review:
languages, entry points, dependency manifests, container/CI/IaC files,
env files, migrations, test folders, and candidate hard-coded secrets.

Standard library only. Never modifies files and never makes network calls.

Usage:
    python3 inventory.py <repo-path> [--json] [--max-file-kb N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv", "env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", "target", ".next", ".nuxt", ".gradle", ".idea", ".vscode",
    "coverage", ".terraform",
}

LANGUAGE_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".scala": "Scala", ".rb": "Ruby",
    ".php": "PHP", ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C",
    ".swift": "Swift", ".sql": "SQL", ".sh": "Shell", ".tf": "Terraform",
}

MANIFESTS = {
    "requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg",
    "poetry.lock", "uv.lock", "Pipfile.lock", "package.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "Gemfile.lock",
    "composer.json", "composer.lock",
}
LOCKFILES = {
    "poetry.lock", "uv.lock", "Pipfile.lock", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "go.sum", "Cargo.lock", "Gemfile.lock", "composer.lock",
}

ENTRY_POINT_NAMES = {
    "main.py", "app.py", "wsgi.py", "asgi.py", "manage.py", "server.py",
    "server.js", "server.ts", "index.js", "index.ts", "app.js", "app.ts",
    "main.go", "main.rs", "Program.cs", "Application.java",
}

CONTAINER_NAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                   "compose.yml", "compose.yaml", ".dockerignore"}

CI_MARKERS = (".github/workflows/", ".gitlab-ci.yml", ".circleci/", "Jenkinsfile",
              "azure-pipelines.yml", "bitbucket-pipelines.yml")

IAC_EXTS = {".tf", ".bicep"}
IAC_DIR_HINTS = ("k8s/", "kubernetes/", "helm/", "charts/", "deploy/", "manifests/")

MIGRATION_DIR_HINTS = ("migrations/", "alembic/", "db/migrate/", "flyway/", "liquibase/")
TEST_DIR_HINTS = ("tests/", "test/", "__tests__/", "spec/")

SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe live key", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b")),
    ("Generic secret assignment", re.compile(
        r"""(?i)\b\w*(?:api[_-]?key|secret|passw(?:or)?d|token|access[_-]?key)\w*\s*[:=]\s*["']([^"'\s]{8,})["']""")),
]
# Values that look like placeholders rather than real secrets.
PLACEHOLDER = re.compile(r"(?i)(changeme|example|your[_-]|xxx+|<.*>|\$\{|\{\{|dummy|test|sample|placeholder)")

TEXT_EXTS = set(LANGUAGE_BY_EXT) | {
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".env", ".conf",
    ".properties", ".xml", ".md", ".txt",
}


@dataclass
class SecretHit:
    file: str
    line: int
    kind: str
    preview: str


@dataclass
class Inventory:
    root: str
    files_scanned: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    manifests: list[str] = field(default_factory=list)
    has_lockfile: bool = False
    containers: list[str] = field(default_factory=list)
    ci: list[str] = field(default_factory=list)
    iac: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    migration_dirs: list[str] = field(default_factory=list)
    test_dirs: list[str] = field(default_factory=list)
    secret_candidates: list[SecretHit] = field(default_factory=list)


def iter_files(root: Path):
    """Yield files under root, pruning dependency and build directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def mask(value: str) -> str:
    """Show only enough of a suspected secret to locate it."""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}…{value[-2:]} ({len(value)} chars)"


def scan_secrets(path: Path, rel: str, max_bytes: int) -> list[SecretHit]:
    if path.stat().st_size > max_bytes:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits: list[SecretHit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            value = match.group(1) if match.groups() else match.group(0)
            if PLACEHOLDER.search(value) or value.startswith(("http://", "https://", "/")):
                continue
            hits.append(SecretHit(rel, lineno, kind, mask(value)))
    return hits


def add_dir_hint(collection: list[str], rel: str, hints: tuple[str, ...]) -> None:
    for hint in hints:
        idx = rel.find(hint)
        if idx != -1:
            directory = rel[: idx + len(hint)].rstrip("/")
            if directory not in collection:
                collection.append(directory)
            return


def build_inventory(root: Path, max_file_kb: int) -> Inventory:
    inv = Inventory(root=str(root))
    languages: Counter[str] = Counter()
    max_bytes = max_file_kb * 1024

    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        name = path.name
        ext = path.suffix.lower()
        inv.files_scanned += 1

        if ext in LANGUAGE_BY_EXT:
            languages[LANGUAGE_BY_EXT[ext]] += 1
        if name in ENTRY_POINT_NAMES or (rel.startswith("cmd/") and name == "main.go"):
            inv.entry_points.append(rel)
        if name in MANIFESTS:
            inv.manifests.append(rel)
            inv.has_lockfile = inv.has_lockfile or name in LOCKFILES
        if name in CONTAINER_NAMES or name.startswith("Dockerfile"):
            inv.containers.append(rel)
        if any(marker in rel or rel == marker for marker in CI_MARKERS):
            inv.ci.append(rel)
        if ext in IAC_EXTS or any(rel.startswith(h) for h in IAC_DIR_HINTS):
            inv.iac.append(rel)
        if name == ".env" or name.startswith(".env."):
            inv.env_files.append(rel)
        add_dir_hint(inv.migration_dirs, rel, MIGRATION_DIR_HINTS)
        add_dir_hint(inv.test_dirs, rel, TEST_DIR_HINTS)

        if ext in TEXT_EXTS or name.startswith(".env") or name.startswith("Dockerfile"):
            inv.secret_candidates.extend(scan_secrets(path, rel, max_bytes))

    inv.languages = dict(languages.most_common())
    return inv


def render_text(inv: Inventory) -> str:
    def section(title: str, items: list[str], empty: str = "none found") -> str:
        body = "\n".join(f"  - {i}" for i in items[:25]) if items else f"  ({empty})"
        more = f"\n  … and {len(items) - 25} more" if len(items) > 25 else ""
        return f"{title}:\n{body}{more}"

    langs = [f"{lang}: {count} files" for lang, count in inv.languages.items()]
    secrets = [f"{h.file}:{h.line}  {h.kind}  {h.preview}" for h in inv.secret_candidates]
    lock_note = "yes" if inv.has_lockfile else "NO lockfile found (unpinned dependencies?)"
    env_note = [f"{e}  <- confirm it is not committed with real values" for e in inv.env_files]

    parts = [
        f"Prodcraft inventory for {inv.root}",
        f"Files scanned: {inv.files_scanned}",
        section("Languages", langs),
        section("Entry points", inv.entry_points),
        section("Dependency manifests", inv.manifests),
        f"Lockfile present: {lock_note}",
        section("Containers", inv.containers),
        section("CI pipelines", inv.ci, "none found — no automated gates?"),
        section("Infrastructure as code", inv.iac),
        section("Env files", env_note),
        section("Migration folders", inv.migration_dirs),
        section("Test folders", inv.test_dirs, "none found — critical paths untested?"),
        section("Secret candidates (verify each; values masked)", secrets),
    ]
    return "\n\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only repo inventory for a production review.")
    parser.add_argument("repo", help="path to the repository root")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--max-file-kb", type=int, default=512,
                        help="skip secret scanning for files larger than this (default 512)")
    args = parser.parse_args(argv)

    root = Path(args.repo).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    inv = build_inventory(root, args.max_file_kb)
    if args.json:
        print(json.dumps(asdict(inv), indent=2))
    else:
        print(render_text(inv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
