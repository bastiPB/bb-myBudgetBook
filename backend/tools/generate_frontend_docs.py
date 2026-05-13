"""
Generate compact frontend orientation docs for Codex work.

Default output is private/local:
  docs/vibe_improvement/generated/FRONTEND_MAP.md

Usage from the repository root:
  python backend/tools/generate_frontend_docs.py

Optional:
  python backend/tools/generate_frontend_docs.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


FROM_IMPORT_RE = re.compile(r"""^\s*import\s+(?!["'])[\s\S]*?\sfrom\s+["']([^"']+)["']""", re.MULTILINE)
SIDE_EFFECT_IMPORT_RE = re.compile(r"""^\s*import\s+["']([^"']+)["']""", re.MULTILINE)
ROUTE_RE = re.compile(r"""<Route\s+path=["']([^"']+)["'][\s\S]*?element=\{([\s\S]*?)\}""")
MODULE_ROUTE_RE = re.compile(r"""key:\s*["']([^"']+)["'][\s\S]*?route:\s*["']([^"']+)["']""")


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel_path: str
    lines: int
    imports: list[str]


def find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / ".git").exists() and (path / "frontend").exists():
            return path
    raise RuntimeError("Could not find repository root.")


def read_source_file(path: Path, repo_root: Path) -> SourceFile:
    text = path.read_text(encoding="utf-8")
    return SourceFile(
        path=path,
        rel_path=path.relative_to(repo_root).as_posix(),
        lines=len(text.splitlines()),
        imports=imports_from_text(text),
    )


def imports_from_text(text: str) -> list[str]:
    imports = FROM_IMPORT_RE.findall(text)
    imports.extend(SIDE_EFFECT_IMPORT_RE.findall(text))
    return imports


def source_files(src_dir: Path, repo_root: Path, subdir: str, suffixes: tuple[str, ...]) -> list[SourceFile]:
    directory = src_dir / subdir
    if not directory.exists():
        return []
    return [
        read_source_file(path, repo_root)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.suffix in suffixes
    ]


def resolve_import(import_path: str, current_file: Path, src_dir: Path, repo_root: Path) -> str:
    if import_path.endswith(".css"):
        base = (current_file.parent / import_path).resolve()
    elif import_path.startswith("."):
        base = (current_file.parent / import_path).resolve()
    elif import_path.startswith("/src/"):
        base = (repo_root / "frontend" / import_path.lstrip("/")).resolve()
    elif import_path.startswith("src/"):
        base = (repo_root / "frontend" / import_path).resolve()
    else:
        return import_path

    candidates = [
        base,
        base.with_suffix(".tsx"),
        base.with_suffix(".ts"),
        base.with_suffix(".css"),
        base / "index.tsx",
        base / "index.ts",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.relative_to(repo_root).as_posix()

    try:
        return base.relative_to(repo_root).as_posix()
    except ValueError:
        return import_path


def compact_paths(paths: list[str], prefix: str) -> str:
    if not paths:
        return "-"
    values = []
    for path in sorted(set(paths)):
        if path.startswith(prefix):
            values.append(f"`{Path(path).name}`")
        else:
            values.append(f"`{path}`")
    return ", ".join(values)


def module_routes(registry_file: Path) -> dict[str, str]:
    if not registry_file.exists():
        return {}

    text = registry_file.read_text(encoding="utf-8")
    return {key: route for key, route in MODULE_ROUTE_RE.findall(text)}


def page_routes(app_file: Path, registry_file: Path) -> dict[str, list[str]]:
    if not app_file.exists():
        return {}

    text = app_file.read_text(encoding="utf-8")
    routes: dict[str, list[str]] = {}
    for path, element in ROUTE_RE.findall(text):
        component_names = re.findall(r"<([A-Z][A-Za-z0-9_]*)\b", element)
        for component_name in component_names:
            routes.setdefault(component_name, []).append(path)

    modules = module_routes(registry_file)
    dynamic_page_by_key = {
        "subscriptions": "SubscriptionsPage",
        "savings_box": "SavingsBoxPage",
    }
    for module_key, page_name in dynamic_page_by_key.items():
        route = modules.get(module_key)
        if route:
            routes.setdefault(page_name, []).append(route)

    return routes


def export_name(file: SourceFile) -> str:
    return file.path.stem


def imports_by_area(file: SourceFile, src_dir: Path, repo_root: Path) -> dict[str, list[str]]:
    areas = {
        "api": [],
        "types": [],
        "components": [],
        "css": [],
        "context": [],
        "other": [],
    }

    for import_path in file.imports:
        resolved = resolve_import(import_path, file.path, src_dir, repo_root)
        if resolved.endswith(".css"):
            areas["css"].append(resolved)
        elif "/api/" in resolved or resolved.startswith("frontend/src/api/"):
            areas["api"].append(resolved)
        elif "/types/" in resolved or resolved.startswith("frontend/src/types/"):
            areas["types"].append(resolved)
        elif "/components/" in resolved or resolved.startswith("frontend/src/components/"):
            areas["components"].append(resolved)
        elif "/context/" in resolved or resolved.startswith("frontend/src/context/"):
            areas["context"].append(resolved)
        elif resolved.startswith("frontend/src/"):
            areas["other"].append(resolved)

    return areas


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def markdown_frontend_map(repo_root: Path) -> str:
    src_dir = repo_root / "frontend" / "src"
    pages = source_files(src_dir, repo_root, "pages", (".tsx", ".ts"))
    components = source_files(src_dir, repo_root, "components", (".tsx", ".ts"))
    api_files = source_files(src_dir, repo_root, "api", (".ts", ".tsx"))
    type_files = source_files(src_dir, repo_root, "types", (".ts", ".tsx"))
    css_files = [
        path
        for path in sorted(src_dir.rglob("*.css"))
        if path.is_file()
    ]
    routes = page_routes(src_dir / "App.tsx", src_dir / "modules" / "registry.ts")

    lines = [
        "# Frontend Map",
        "",
        "Generated from `frontend/src`. Do not edit manually.",
        "",
        "Run:",
        "",
        "```powershell",
        "python backend/tools/generate_frontend_docs.py",
        "```",
        "",
        "Use this as the first read before frontend changes. It shows likely edit locations without loading large TSX/CSS files.",
        "",
        "## Pages",
        "",
        "| Page | Lines | Route(s) | CSS | API Imports | Type Imports | Component Imports |",
        "|---|---:|---|---|---|---|---|",
    ]

    for page in pages:
        areas = imports_by_area(page, src_dir, repo_root)
        route_values = routes.get(export_name(page), [])
        lines.append(
            "| "
            f"`{page.rel_path}` | "
            f"{page.lines} | "
            f"{markdown_cell(', '.join(f'`{route}`' for route in route_values) or '-')} | "
            f"{markdown_cell(compact_paths(areas['css'], 'frontend/src/pages/'))} | "
            f"{markdown_cell(compact_paths(areas['api'], 'frontend/src/api/'))} | "
            f"{markdown_cell(compact_paths(areas['types'], 'frontend/src/types/'))} | "
            f"{markdown_cell(compact_paths(areas['components'], 'frontend/src/components/'))} |"
        )

    lines.extend(
        [
            "",
            "## API Wrappers",
            "",
            "| File | Lines | Imports |",
            "|---|---:|---|",
        ]
    )
    for api_file in api_files:
        internal_imports = [
            resolve_import(item, api_file.path, src_dir, repo_root)
            for item in api_file.imports
            if item.startswith(".") or item.startswith("src/") or item.startswith("/src/")
        ]
        lines.append(
            "| "
            f"`{api_file.rel_path}` | "
            f"{api_file.lines} | "
            f"{markdown_cell(compact_paths(internal_imports, 'frontend/src/'))} |"
        )

    lines.extend(
        [
            "",
            "## Components",
            "",
            "| Component | Lines | CSS | API Imports | Type Imports |",
            "|---|---:|---|---|---|",
        ]
    )
    for component in components:
        areas = imports_by_area(component, src_dir, repo_root)
        lines.append(
            "| "
            f"`{component.rel_path}` | "
            f"{component.lines} | "
            f"{markdown_cell(compact_paths(areas['css'], 'frontend/src/components/'))} | "
            f"{markdown_cell(compact_paths(areas['api'], 'frontend/src/api/'))} | "
            f"{markdown_cell(compact_paths(areas['types'], 'frontend/src/types/'))} |"
        )

    lines.extend(
        [
            "",
            "## Types",
            "",
            "| File | Lines |",
            "|---|---:|",
        ]
    )
    for type_file in type_files:
        lines.append(f"| `{type_file.rel_path}` | {type_file.lines} |")

    lines.extend(
        [
            "",
            "## CSS Files",
            "",
            "| File | Lines |",
            "|---|---:|",
        ]
    )
    for css_file in css_files:
        line_count = len(css_file.read_text(encoding="utf-8").splitlines())
        lines.append(f"| `{css_file.relative_to(repo_root).as_posix()}` | {line_count} |")

    lines.extend(
        [
            "",
            "## Efficient Read Workflow",
            "",
            "1. Read this file first to identify the likely page/API/type/CSS files.",
            "2. Use `rg` to find the exact symbol, class, or text.",
            "3. Read only the relevant line window before editing.",
            "4. For API contracts, cross-check `API_MAP.md` and `API_SCHEMAS.md`.",
            "",
        ]
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate frontend orientation docs.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to docs/vibe_improvement/generated.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether generated files are up to date without writing them.",
    )
    return parser.parse_args()


def check_output(path: Path, expected_content: str, repo_root: Path) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == expected_content:
        print("Frontend docs are up to date.")
        return True

    print("Frontend docs are stale. Regenerate them with:")
    print("  python backend/tools/generate_frontend_docs.py")
    print()
    print(f"Stale file: {path.relative_to(repo_root)}")
    return False


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    output_dir = Path(args.output_dir) if args.output_dir else repo_root / "docs" / "vibe_improvement" / "generated"
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    output_path = output_dir / "FRONTEND_MAP.md"
    content = markdown_frontend_map(repo_root)

    if args.check:
        if not check_output(output_path, content, repo_root):
            sys.exit(1)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
