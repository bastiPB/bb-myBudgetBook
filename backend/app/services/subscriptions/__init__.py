"""
app/services/subscriptions/ — Business-Logik fuer Abo-Operationen.

Diese Schicht kennt KEIN HTTP (kein Request, kein Response).
Alle oeffentlichen Funktionen pruefen: darf dieser User dieses Abo sehen / aendern?

Paket-Split (v0.2.5): Untermodule nach Verantwortlichkeit; Imports bleiben
`from app.services.subscriptions import ...` stabil.
"""

from .billing import (
    applicable_billing_terms,
    applicable_price,
    compute_dieses_kalenderjahr,
    compute_due_dates,
    compute_due_dates_for_billing_history,
    compute_intervalle,
    compute_next_due_date,
    compute_next_due_date_from_history,
    compute_tatsaechlich,
    is_in_pause,
    sync_subscription_billing_snapshot,
)
from .constants import (
    _ALLOWED_LOGO_TYPES,
    _LOGO_EXT,
    _MAX_LOGO_SIZE_BYTES,
    _MONTHLY_FACTOR,
    _MONTHS_PER_PERIOD,
)
from .lifecycle import (
    cancel_subscription,
    delete_subscription,
    resume_subscription,
    suspend_subscription,
)
from .logos import upload_subscription_logo
from .mutations import (
    create_subscription,
    delete_billing_history_entry,
    delete_price_history_entry,
    interval_change,
    price_change,
    update_subscription,
)
from .readers import (
    get_billing_history,
    get_overview,
    get_price_history,
    get_scheduled_payments,
    get_subscription,
    get_subscription_detail,
    list_subscriptions,
    subscription_to_read,
)
from .types import ComputedDue, OverviewResult

__all__ = [
    "ComputedDue",
    "OverviewResult",
    "_ALLOWED_LOGO_TYPES",
    "_LOGO_EXT",
    "_MAX_LOGO_SIZE_BYTES",
    "_MONTHLY_FACTOR",
    "_MONTHS_PER_PERIOD",
    "applicable_billing_terms",
    "applicable_price",
    "cancel_subscription",
    "compute_dieses_kalenderjahr",
    "compute_due_dates",
    "compute_due_dates_for_billing_history",
    "compute_intervalle",
    "compute_next_due_date",
    "compute_next_due_date_from_history",
    "compute_tatsaechlich",
    "create_subscription",
    "delete_billing_history_entry",
    "delete_price_history_entry",
    "delete_subscription",
    "get_billing_history",
    "get_overview",
    "get_price_history",
    "get_scheduled_payments",
    "get_subscription",
    "get_subscription_detail",
    "interval_change",
    "is_in_pause",
    "list_subscriptions",
    "price_change",
    "resume_subscription",
    "subscription_to_read",
    "suspend_subscription",
    "sync_subscription_billing_snapshot",
    "update_subscription",
    "upload_subscription_logo",
]
