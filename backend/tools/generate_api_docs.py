"""
Generate compact API documentation from the FastAPI OpenAPI schema.

Default output is private/local:
  docs/vibe_improvement/generated/openapi.json
  docs/vibe_improvement/generated/API_MAP.md
  docs/vibe_improvement/generated/API_SCHEMAS.md

Usage from the repository root:
  python backend/tools/generate_api_docs.py

Usage from backend/:
  python tools/generate_api_docs.py

Optional:
  python backend/tools/generate_api_docs.py --output-dir docs
  python backend/tools/generate_api_docs.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute


HTTP_METHOD_ORDER = {
    "GET": 0,
    "POST": 1,
    "PUT": 2,
    "PATCH": 3,
    "DELETE": 4,
    "OPTIONS": 5,
    "HEAD": 6,
}

ACCESS_BY_DEPENDENCY = {
    "_get_admin_user": "admin",
    "_get_editor_or_admin_user": "editor/admin",
    "_get_current_user": "authenticated",
}

ACCESS_RANK = {
    "public": 0,
    "authenticated": 1,
    "editor/admin": 2,
    "admin": 3,
}


@dataclass(frozen=True)
class EndpointRow:
    method: str
    path: str
    tag: str
    operation: str
    request: str
    response: str
    access: str


def find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / ".git").exists() and (path / "backend").exists():
            return path
    raise RuntimeError("Could not find repository root.")


def ensure_backend_on_path(repo_root: Path) -> None:
    backend_path = repo_root / "backend"
    sys.path.insert(0, str(backend_path))


def schema_name(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "-"

    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", 1)[-1]

    schema_type = schema.get("type")
    if schema_type == "array":
        return f"{schema_name(schema.get('items'))}[]"

    for key in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(key)
        if isinstance(variants, list) and variants:
            names = [schema_name(item) for item in variants if isinstance(item, dict)]
            names = [name for name in names if name != "-"]
            return " | ".join(names) if names else "-"

    title = schema.get("title")
    if isinstance(title, str):
        return title

    if isinstance(schema_type, str):
        return schema_type

    return "object"


def request_name(operation: dict[str, Any]) -> str:
    body = operation.get("requestBody")
    if not isinstance(body, dict):
        return "-"

    content = body.get("content")
    if not isinstance(content, dict):
        return "-"

    for media_type in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
        media = content.get(media_type)
        if isinstance(media, dict):
            name = schema_name(media.get("schema"))
            if media_type == "application/json":
                return name
            return f"{name} ({media_type})"

    first_media = next(iter(content.values()), None)
    if isinstance(first_media, dict):
        return schema_name(first_media.get("schema"))

    return "-"


def response_name(operation: dict[str, Any]) -> str:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return "-"

    for status_code in ("200", "201", "202", "204"):
        response = responses.get(status_code)
        if isinstance(response, dict):
            if status_code == "204":
                return "no content"
            content = response.get("content")
            if isinstance(content, dict):
                media = content.get("application/json") or next(iter(content.values()), None)
                if isinstance(media, dict):
                    return schema_name(media.get("schema"))
            return "-"

    return "-"


def route_access(route: APIRoute) -> str:
    dependency_names: set[str] = set()

    def walk(dependant: Any) -> None:
        for dependency in getattr(dependant, "dependencies", []):
            call = getattr(dependency, "call", None)
            name = getattr(call, "__name__", None)
            if isinstance(name, str):
                dependency_names.add(name)
            walk(dependency)

    walk(route.dependant)

    access = "public"
    for dependency_name in dependency_names:
        candidate = ACCESS_BY_DEPENDENCY.get(dependency_name)
        if candidate and ACCESS_RANK[candidate] > ACCESS_RANK[access]:
            access = candidate

    return access


def build_access_lookup(app: Any) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            lookup[(method.upper(), route.path)] = route_access(route)
    return lookup


def build_rows(openapi: dict[str, Any], access_lookup: dict[tuple[str, str], str]) -> list[EndpointRow]:
    rows: list[EndpointRow] = []
    paths = openapi.get("paths", {})

    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue

        for method, operation in methods.items():
            method_upper = method.upper()
            if method_upper not in HTTP_METHOD_ORDER or not isinstance(operation, dict):
                continue

            tags = operation.get("tags") or ["-"]
            tag = str(tags[0]) if tags else "-"
            rows.append(
                EndpointRow(
                    method=method_upper,
                    path=path,
                    tag=tag,
                    operation=str(operation.get("operationId") or "-"),
                    request=request_name(operation),
                    response=response_name(operation),
                    access=access_lookup.get((method_upper, path), "unknown"),
                )
            )

    return sorted(rows, key=lambda row: (row.path, HTTP_METHOD_ORDER.get(row.method, 99), row.method))


def markdown_table(rows: list[EndpointRow]) -> str:
    lines = [
        "# API Map",
        "",
        "Generated from FastAPI OpenAPI. Do not edit manually.",
        "",
        "Run:",
        "",
        "```powershell",
        "python backend/tools/generate_api_docs.py",
        "```",
        "",
        "| Method | Path | Tag | Access | Operation | Request | Response |",
        "|---|---|---|---|---|---|---|",
    ]

    for row in rows:
        lines.append(
            "| "
            f"{row.method} | "
            f"`{row.path}` | "
            f"{markdown_cell(row.tag)} | "
            f"{markdown_cell(row.access)} | "
            f"`{markdown_cell(row.operation)}` | "
            f"{markdown_cell(row.request)} | "
            f"{markdown_cell(row.response)} |"
        )

    lines.extend(
        [
            "",
            "## Access Legend",
            "",
            "- `public`: no authentication dependency detected.",
            "- `authenticated`: requires a logged-in user.",
            "- `editor/admin`: requires editor or admin role.",
            "- `admin`: requires admin role.",
            "- `unknown`: route was present in OpenAPI but no matching FastAPI route was found.",
            "",
            "Access is inferred from FastAPI dependencies and should be checked before security-sensitive changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def schema_type(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "-"

    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", 1)[-1]

    enum = schema.get("enum")
    if isinstance(enum, list):
        return "enum: " + ", ".join(str(item) for item in enum)

    schema_type_value = schema.get("type")
    if schema_type_value == "array":
        return f"{schema_type(schema.get('items'))}[]"

    for key in ("anyOf", "oneOf", "allOf"):
        variants = schema.get(key)
        if isinstance(variants, list) and variants:
            names = [schema_type(item) for item in variants if isinstance(item, dict)]
            names = [name for name in names if name != "-"]
            return " | ".join(names) if names else "-"

    if schema_type_value == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"object<string, {schema_type(additional)}>"
        return "object"

    schema_format = schema.get("format")
    if isinstance(schema_type_value, str) and isinstance(schema_format, str):
        return f"{schema_type_value}({schema_format})"

    if isinstance(schema_type_value, str):
        return schema_type_value

    title = schema.get("title")
    if isinstance(title, str):
        return title

    return "object"


def schema_description(schema: dict[str, Any]) -> str:
    description = schema.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip().replace("\n", " ")
    return "-"


def markdown_schema_docs(openapi: dict[str, Any]) -> str:
    schemas = openapi.get("components", {}).get("schemas", {})
    lines = [
        "# API Schemas",
        "",
        "Generated from FastAPI OpenAPI. Do not edit manually.",
        "",
        "This is a compact schema overview for Codex/frontend work. Use `openapi.json` for full details.",
        "",
    ]

    if not isinstance(schemas, dict) or not schemas:
        lines.append("No schemas found.")
        return "\n".join(lines) + "\n"

    for name in sorted(schemas):
        schema = schemas[name]
        if not isinstance(schema, dict):
            continue

        lines.append(f"## {name}")
        lines.append("")

        properties = schema.get("properties")
        required = set(schema.get("required") or [])

        if isinstance(properties, dict) and properties:
            lines.append("| Field | Type | Required | Description |")
            lines.append("|---|---|---|---|")
            for field_name in sorted(properties):
                field_schema = properties[field_name]
                if not isinstance(field_schema, dict):
                    continue
                is_required = "yes" if field_name in required else "no"
                lines.append(
                    "| "
                    f"`{field_name}` | "
                    f"{markdown_cell(schema_type(field_schema))} | "
                    f"{is_required} | "
                    f"{markdown_cell(schema_description(field_schema))} |"
                )
            lines.append("")
            continue

        lines.append(f"Type: `{markdown_cell(schema_type(schema))}`")
        description = schema_description(schema)
        if description != "-":
            lines.append("")
            lines.append(description)
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate API docs from FastAPI OpenAPI.")
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


def check_outputs(outputs: dict[Path, str], repo_root: Path) -> bool:
    stale_paths: list[Path] = []
    for path, expected_content in outputs.items():
        if not path.exists():
            stale_paths.append(path)
            continue

        actual_content = path.read_text(encoding="utf-8")
        if actual_content != expected_content:
            stale_paths.append(path)

    if not stale_paths:
        print("API docs are up to date.")
        return True

    print("API docs are stale. Regenerate them with:")
    print("  python backend/tools/generate_api_docs.py")
    print()
    print("Stale files:")
    for path in stale_paths:
        print(f"  {path.relative_to(repo_root)}")
    return False


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    ensure_backend_on_path(repo_root)

    from app.main import create_app

    app = create_app()
    openapi = app.openapi()
    access_lookup = build_access_lookup(app)
    rows = build_rows(openapi, access_lookup)

    output_dir = Path(args.output_dir) if args.output_dir else repo_root / "docs" / "vibe_improvement" / "generated"
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    openapi_path = output_dir / "openapi.json"
    api_map_path = output_dir / "API_MAP.md"
    api_schemas_path = output_dir / "API_SCHEMAS.md"

    outputs = {
        openapi_path: json.dumps(openapi, indent=2, sort_keys=True),
        api_map_path: markdown_table(rows),
        api_schemas_path: markdown_schema_docs(openapi),
    }

    if args.check:
        if not check_outputs(outputs, repo_root):
            sys.exit(1)
        return

    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")

    print(f"Wrote {openapi_path.relative_to(repo_root)}")
    print(f"Wrote {api_map_path.relative_to(repo_root)}")
    print(f"Wrote {api_schemas_path.relative_to(repo_root)}")
    print(f"Documented {len(rows)} endpoints.")


if __name__ == "__main__":
    main()
