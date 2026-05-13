"""
Generate a compact pattern index from known code anchors.

Default output is private/local:
  docs/vibe_improvement/generated/PATTERN_INDEX.md

Usage from the repository root:
  python backend/tools/generate_pattern_docs.py

Optional:
  python backend/tools/generate_pattern_docs.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Anchor:
    label: str
    path: str
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class PatternDoc:
    title: str
    purpose: str
    rule: str
    domain_keys: tuple[str, ...]
    anchors: tuple[Anchor, ...]


PATTERNS: tuple[PatternDoc, ...] = (
    PatternDoc(
        title="Subscription Tags",
        purpose="Tag CRUD, tag assignment, and list/detail tag loading.",
        rule=(
            "List views use bulk_load_tags plus _computed_tags to avoid N+1 queries. "
            "Detail views use get_tags_for_subscription for one subscription."
        ),
        domain_keys=("subscriptions",),
        anchors=(
            Anchor("Tag router", "backend/app/routers/subscription_tags.py", ("APIRouter", "assign_tags_to_subscription")),
            Anchor("Tag service", "backend/app/services/subscriptions/tags.py", ("set_subscription_tags", "bulk_load_tags")),
            Anchor("List tag cache", "backend/app/services/subscriptions/readers.py", ("bulk_load_tags", "_computed_tags")),
            Anchor("Frontend tag API", "frontend/src/api/tags.ts", ("getTags", "setSubscriptionTags")),
            Anchor("Tag selector", "frontend/src/components/TagSelector.tsx", ("TagSelector",)),
            Anchor("Tag management", "frontend/src/components/TagManagementModal.tsx", ("TagManagementModal",)),
        ),
    ),
    PatternDoc(
        title="Subscription Billing History",
        purpose="Amount, interval, anchor dates, due dates, and billing projections.",
        rule=(
            "Billing history is the source of truth for amount + interval + anchor. "
            "Snapshot fields are synchronized with sync_subscription_billing_snapshot."
        ),
        domain_keys=("subscriptions",),
        anchors=(
            Anchor("Billing functions", "backend/app/services/subscriptions/billing.py", (
                "compute_due_dates_for_billing_history",
                "sync_subscription_billing_snapshot",
                "applicable_billing_terms",
            )),
            Anchor("Billing mutations", "backend/app/services/subscriptions/mutations.py", (
                "IntervalChangeRequest",
                "PriceChangeRequest",
                "delete_billing_history_entry",
            )),
            Anchor("Billing router", "backend/app/routers/subscriptions.py", (
                "billing_history",
                "interval_change_endpoint",
                "price_change_endpoint",
            )),
            Anchor("Subscription detail UI", "frontend/src/pages/SubscriptionDetailPage.tsx", (
                "getBillingHistory",
                "intervalChange",
                "priceChange",
            )),
        ),
    ),
    PatternDoc(
        title="Subscription Price History",
        purpose="Legacy/price-only history and deletion safety.",
        rule=(
            "Price-entry deletion is blocked when it removes the only price or affects scheduled payments "
            "inside the entry validity window."
        ),
        domain_keys=("subscriptions",),
        anchors=(
            Anchor("Price deletion", "backend/app/services/subscriptions/mutations.py", (
                "delete_price_history_entry",
                "PriceEntryDeleteBlockedError",
                "applicable_price",
            )),
            Anchor("Price router", "backend/app/routers/subscriptions.py", (
                "price_history",
                "delete_price_history_entry_endpoint",
                "price_change_endpoint",
            )),
            Anchor("Price frontend API", "frontend/src/api/subscriptions.ts", (
                "getPriceHistory",
                "deletePriceHistoryEntry",
                "priceChange",
            )),
        ),
    ),
    PatternDoc(
        title="Subscription Lifecycle",
        purpose="Suspend, resume, cancel, and pause-history behavior.",
        rule=(
            "active can be suspended, suspended can be resumed, canceled is final. "
            "Pause history marks suspended periods and final cancellation boundaries."
        ),
        domain_keys=("subscriptions",),
        anchors=(
            Anchor("Lifecycle service", "backend/app/services/subscriptions/lifecycle.py", (
                "suspend_subscription",
                "resume_subscription",
                "cancel_subscription",
            )),
            Anchor("Lifecycle router", "backend/app/routers/subscriptions.py", (
                "/{subscription_id}/suspend",
                "/{subscription_id}/resume",
                "/{subscription_id}/cancel",
            )),
            Anchor("List lifecycle UI", "frontend/src/pages/SubscriptionsPage.tsx", (
                "suspendSubscription",
                "resumeSubscription",
            )),
            Anchor("Detail lifecycle UI", "frontend/src/pages/SubscriptionDetailPage.tsx", (
                "cancelSubscription",
                "suspendSubscription",
                "resumeSubscription",
            )),
        ),
    ),
    PatternDoc(
        title="Scheduled Payments",
        purpose="Period-based scheduled payment generation.",
        rule=(
            "Scheduler due_date is the computed billing due date, not the run date. "
            "Catch-up uses scheduler_catch_up_days and idempotency is protected before insert."
        ),
        domain_keys=("subscriptions",),
        anchors=(
            Anchor("Scheduler", "backend/app/services/scheduler_service.py", (
                "generate_scheduled_payments",
                "scheduler_catch_up_days",
                "compute_due_dates_for_billing_history",
                "is_in_pause",
            )),
            Anchor("Admin trigger", "backend/app/routers/admin.py", ("trigger_payments",)),
            Anchor("Scheduled payment schema/API", "frontend/src/api/subscriptions.ts", ("getScheduledPayments",)),
            Anchor("Scheduled payment UI", "frontend/src/pages/SubscriptionDetailPage.tsx", ("getScheduledPayments",)),
        ),
    ),
    PatternDoc(
        title="Module Configuration",
        purpose="Feature/module availability in UI and per-user module config.",
        rule=(
            "Frontend routes are driven by activeModules and registry entries. "
            "Adding a module requires registry plus backend module key support."
        ),
        domain_keys=("*",),
        anchors=(
            Anchor("Frontend registry", "frontend/src/modules/registry.ts", ("MODULE_REGISTRY", "route")),
            Anchor("App dynamic routes", "frontend/src/App.tsx", ("activeModules.map", "module.key")),
            Anchor("Module provider", "frontend/src/context/ModulesProvider.tsx", ("activeModules",)),
            Anchor("Backend profile service", "backend/app/services/profile.py", ("MODULE_KEYS",)),
            Anchor("Module config router", "backend/app/routers/profile.py", ("module-config",)),
        ),
    ),
    PatternDoc(
        title="Savings Box Terms",
        purpose="Savings term generation, missed-term refresh, penalties, and summaries.",
        rule=(
            "Terms are generated from start_date to end_date. Detail/terms/bookings reads refresh overdue "
            "open terms and create idempotent penalty bookings for missed terms."
        ),
        domain_keys=("savings_box",),
        anchors=(
            Anchor("Savings terms service", "backend/app/services/savings/terms.py", (
                "generate_terms",
                "update_term_statuses",
                "compute_box_summary",
            )),
            Anchor("Savings readers", "backend/app/services/savings/readers.py", (
                "get_box_detail",
                "update_term_statuses",
                "compute_box_summary",
            )),
            Anchor("Savings router", "backend/app/routers/savings.py", (
                "/{box_id}/terms",
                "/{box_id}/terms/refresh",
                "/{box_id}/bookings",
            )),
            Anchor("Savings frontend API", "frontend/src/api/savingsBox.ts", (
                "getBoxTerms",
                "refreshTerms",
                "getBoxBookings",
            )),
            Anchor("Savings detail UI", "frontend/src/pages/SavingsBoxDetailPage.tsx", (
                "SavingsBoxDetail",
                "booking_type",
                "terms",
            )),
        ),
    ),
    PatternDoc(
        title="Savings Box Bookings",
        purpose="Deposit, penalty, and manual booking rules.",
        rule=(
            "Deposits require a term and must meet expected_amount. Penalty bookings require a term. "
            "Manual bookings may exist without a term and do not count as deposited or penalty summary amounts."
        ),
        domain_keys=("savings_box",),
        anchors=(
            Anchor("Savings mutations", "backend/app/services/savings/mutations.py", (
                "create_booking",
                "_sync_term_and_penalty_after_deposit_change",
                "SavingsPenaltyDeleteBlockedError",
            )),
            Anchor("Savings models", "backend/app/models/savings_box.py", (
                "SavingsBookingType",
                "SavingsTermStatus",
                "SavingsBooking",
            )),
            Anchor("Savings schemas", "backend/app/schemas/savings_box.py", (
                "SavingsBookingCreate",
                "SavingsBookingUpdate",
                "SavingsBookingRead",
            )),
            Anchor("Savings detail UI", "frontend/src/pages/SavingsBoxDetailPage.tsx", (
                "depositForm",
                "editBooking",
                "deleteBooking",
            )),
        ),
    ),
    PatternDoc(
        title="Savings Box Lifecycle",
        purpose="Closing and reopening savings boxes.",
        rule=(
            "Closed boxes are immutable for normal mutations. Closing stores expected/actual closing values; "
            "reopening clears closing fields and returns the box to active."
        ),
        domain_keys=("savings_box",),
        anchors=(
            Anchor("Savings lifecycle", "backend/app/services/savings/lifecycle.py", (
                "close_savings_box",
                "reopen_savings_box",
                "closing_expected_amount",
            )),
            Anchor("Savings access", "backend/app/services/savings/access.py", ("assert_box_is_open",)),
            Anchor("Savings router", "backend/app/routers/savings.py", (
                "/{box_id}/close",
                "/{box_id}/reopen",
            )),
            Anchor("Savings frontend API", "frontend/src/api/savingsBox.ts", (
                "closeBox",
                "reopenBox",
            )),
            Anchor("Savings detail UI", "frontend/src/pages/SavingsBoxDetailPage.tsx", (
                "closeForm",
                "closeBox",
                "reopenBox",
            )),
        ),
    ),
)


def find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / ".git").exists() and (path / "backend").exists() and (path / "frontend").exists():
            return path
    raise RuntimeError("Could not find repository root.")


def line_matches(path: Path, patterns: tuple[str, ...]) -> list[str]:
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    matches: list[str] = []
    for pattern in patterns:
        matcher = re.compile(re.escape(pattern))
        for line_number, line in enumerate(lines, start=1):
            if matcher.search(line):
                matches.append(f"`{pattern}` at line {line_number}")
                break
        else:
            matches.append(f"`{pattern}` missing")
    return matches


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def module_registry_entries(repo_root: Path) -> list[dict[str, str]]:
    registry_path = repo_root / "frontend/src/modules/registry.ts"
    if not registry_path.exists():
        return []

    text = registry_path.read_text(encoding="utf-8")
    entries: list[dict[str, str]] = []
    blocks = re.findall(r"\{([\s\S]*?)\}", text)
    for block in blocks:
        key = _field_value(block, "key")
        if not key:
            continue
        entries.append(
            {
                "key": key,
                "label": _field_value(block, "label") or "-",
                "route": _field_value(block, "route") or "-",
                "navLabel": _field_value(block, "navLabel") or "-",
            }
        )
    return entries


def _field_value(block: str, field_name: str) -> str | None:
    match = re.search(rf"{field_name}:\s*['\"]([^'\"]+)['\"]", block)
    return match.group(1) if match else None


def covered_domain_keys() -> set[str]:
    keys: set[str] = set()
    for pattern in PATTERNS:
        for key in pattern.domain_keys:
            if key != "*":
                keys.add(key)
    return keys


def domain_coverage_section(repo_root: Path) -> list[str]:
    entries = module_registry_entries(repo_root)
    covered = covered_domain_keys()
    lines = [
        "",
        "## Domain Coverage",
        "",
        "Generated from `frontend/src/modules/registry.ts` and pattern metadata.",
        "",
        "| Module Key | Label | Route | Pattern Coverage |",
        "|---|---|---|---|",
    ]
    if not entries:
        lines.append("| - | - | - | registry not found |")
        return lines

    for entry in entries:
        key = entry["key"]
        status = "covered" if key in covered else "missing pattern docs"
        lines.append(
            "| "
            f"`{markdown_cell(key)}` | "
            f"{markdown_cell(entry['label'])} | "
            f"`{markdown_cell(entry['route'])}` | "
            f"{status} |"
        )
    return lines


def markdown_pattern_index(repo_root: Path) -> str:
    lines = [
        "# Pattern Index",
        "",
        "Generated from known code anchors. Do not edit manually.",
        "",
        "Run:",
        "",
        "```powershell",
        "python backend/tools/generate_pattern_docs.py",
        "```",
        "",
        "This file keeps semantic pattern entry points current. It does not prove that a business rule is still correct; it shows where to verify it quickly.",
        "",
        "## Summary",
        "",
        "| Pattern | Purpose | Rule | Status |",
        "|---|---|---|---|",
    ]

    pattern_status: dict[str, str] = {}
    for pattern in PATTERNS:
        missing = 0
        for anchor in pattern.anchors:
            anchor_path = repo_root / anchor.path
            matches = line_matches(anchor_path, anchor.patterns)
            missing += sum(1 for item in matches if item.endswith("missing"))
            if not anchor_path.exists():
                missing += 1
        status = "ok" if missing == 0 else f"check ({missing} missing)"
        pattern_status[pattern.title] = status
        lines.append(
            "| "
            f"{markdown_cell(pattern.title)} | "
            f"{markdown_cell(pattern.purpose)} | "
            f"{markdown_cell(pattern.rule)} | "
            f"{status} |"
        )

    for pattern in PATTERNS:
        lines.extend(["", f"## {pattern.title}", "", pattern.rule, ""])
        lines.extend(
            [
                "| Anchor | File | Matches |",
                "|---|---|---|",
            ]
        )
        for anchor in pattern.anchors:
            anchor_path = repo_root / anchor.path
            if not anchor_path.exists():
                match_text = "file missing"
            else:
                match_text = ", ".join(line_matches(anchor_path, anchor.patterns))
            lines.append(
                "| "
                f"{markdown_cell(anchor.label)} | "
                f"`{anchor.path}` | "
                f"{markdown_cell(match_text)} |"
            )

    lines.extend(domain_coverage_section(repo_root))
    lines.extend(
        [
            "",
            "## How To Use",
            "",
            "1. Use this file to find the current code anchors for a known pattern.",
            "2. If a status says `check`, inspect the listed file and update the pattern definition or implementation.",
            "3. Use Domain Coverage to spot modules that exist in the registry but have no pattern documentation yet.",
            "4. Keep detailed generated structure in `FRONTEND_MAP.md`, `API_MAP.md`, and `API_SCHEMAS.md`.",
            "",
        ]
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pattern index from known anchors.")
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
        print("Pattern docs are up to date.")
        return True

    print("Pattern docs are stale. Regenerate them with:")
    print("  python backend/tools/generate_pattern_docs.py")
    print()
    print(f"Stale file: {path.relative_to(repo_root)}")
    return False


def main() -> None:
    args = parse_args()
    repo_root = find_repo_root(Path(__file__).resolve())
    output_dir = Path(args.output_dir) if args.output_dir else repo_root / "docs" / "vibe_improvement" / "generated"
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    output_path = output_dir / "PATTERN_INDEX.md"
    content = markdown_pattern_index(repo_root)

    if args.check:
        if not check_output(output_path, content, repo_root):
            sys.exit(1)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
