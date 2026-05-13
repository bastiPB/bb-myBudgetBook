"""
Generate the private Vibe Improvement README.

Default output:
  docs/vibe_improvement/README.md

Usage from the repository root:
  python backend/tools/generate_vibe_readme.py

Optional:
  python backend/tools/generate_vibe_readme.py --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


GENERATORS = (
    ("API docs", "backend/tools/generate_api_docs.py"),
    ("Frontend docs", "backend/tools/generate_frontend_docs.py"),
    ("Pattern index", "backend/tools/generate_pattern_docs.py"),
    ("Vibe README", "backend/tools/generate_vibe_readme.py"),
)

READ_ORDER = (
    "generated/FRONTEND_MAP.md",
    "generated/API_MAP.md",
    "generated/API_SCHEMAS.md",
    "generated/PATTERN_INDEX.md",
    "02-important-patterns.md",
    "03-change-brief-template.md",
)


def find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / ".git").exists() and (path / "backend").exists() and (path / "frontend").exists():
            return path
    raise RuntimeError("Could not find repository root.")


def sorted_relative_files(directory: Path, root: Path, pattern: str = "*") -> list[str]:
    if not directory.exists():
        return []
    return [
        path.relative_to(root).as_posix()
        for path in sorted(directory.glob(pattern))
        if path.is_file()
    ]


def existing_generator_commands(repo_root: Path, suffix: str = "") -> list[str]:
    commands: list[str] = []
    for _label, rel_path in GENERATORS:
        if (repo_root / rel_path).exists():
            commands.append(f"python {rel_path}{suffix}")
    return commands


def code_block(lines: list[str], language: str = "text") -> list[str]:
    if not lines:
        return [f"```{language}", "-", "```"]
    return [f"```{language}", *lines, "```"]


def markdown_readme(repo_root: Path) -> str:
    vibe_dir = repo_root / "docs" / "vibe_improvement"
    generated_dir = vibe_dir / "generated"

    generated_files = sorted_relative_files(generated_dir, vibe_dir)
    manual_files = [
        Path(path).name
        for path in sorted_relative_files(vibe_dir, vibe_dir, "*.md")
        if Path(path).name != "README.md"
    ]

    lines = [
        "# Vibe Improvement",
        "",
        "Generated private README. Do not edit manually.",
        "",
        "Status: private working notes",
        "Git: this folder is ignored via `.git/info/exclude` and must not be committed.",
        "",
        "## Read Order For Codex",
        "",
        "Use this order before implementation work:",
        "",
    ]
    lines.extend(f"{index}. `{item}`" for index, item in enumerate(READ_ORDER, start=1))

    lines.extend(
        [
            "",
            "## Generated Files",
            "",
            "These files are generated and should not be edited manually:",
            "",
        ]
    )
    lines.extend(code_block(generated_files))

    lines.extend(
        [
            "",
            "Regenerate manually:",
            "",
        ]
    )
    lines.extend(code_block(existing_generator_commands(repo_root), "powershell"))

    lines.extend(
        [
            "",
            "Check manually:",
            "",
        ]
    )
    lines.extend(code_block(existing_generator_commands(repo_root, " --check"), "powershell"))

    lines.extend(
        [
            "",
            "Local hooks regenerate private generated files on:",
            "",
            "- pre-commit",
            "- post-checkout",
            "- post-merge",
            "",
            "## Manual Files",
            "",
            "These files are curated notes:",
            "",
        ]
    )
    lines.extend(code_block(manual_files))

    lines.extend(
        [
            "",
            "Keep manual files short. If a note becomes repetitive or structural, prefer a generator.",
            "",
            "## New Domain Workflow",
            "",
            "When a new module/domain is added, for example `vacation_fund`:",
            "",
            "1. Add the module to `frontend/src/modules/registry.ts`.",
            "2. Add backend support such as models, schemas, router, service, and tests as needed.",
            "3. Run `python backend/tools/generate_pattern_docs.py`.",
            "4. Check `generated/PATTERN_INDEX.md` -> `Domain Coverage`.",
            "5. If the module says `missing pattern docs`, add one or more PatternDoc entries in `backend/tools/generate_pattern_docs.py`.",
            "6. Add a short semantic explanation to `02-important-patterns.md` only when the domain has non-obvious business rules.",
            "",
            "Rule:",
            "",
            "```text",
            "Generated files keep anchors current.",
            "Manual files explain business meaning.",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate private vibe improvement README.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether README is up to date without writing it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    output_path = repo_root / "docs" / "vibe_improvement" / "README.md"
    content = markdown_readme(repo_root)

    if args.check:
        if output_path.exists() and output_path.read_text(encoding="utf-8") == content:
            print("Vibe README is up to date.")
            return
        print("Vibe README is stale. Regenerate it with:")
        print("  python backend/tools/generate_vibe_readme.py")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
