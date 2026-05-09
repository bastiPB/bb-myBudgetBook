"""
Öffentliche Sparfach-Service-API — importiere von hier: from app.services.savings import ...
"""

from .access import get_box_or_404
from .lifecycle import close_savings_box, reopen_savings_box
from .mutations import (
    create_booking,
    create_box,
    delete_booking,
    update_booking,
    update_box,
)
from .readers import (
    box_summary_to_read,
    get_box_detail,
    get_box_list_projection,
    list_boxes,
    savings_box_to_detail,
    savings_box_to_read,
)
from .terms import update_term_statuses

__all__ = [
    "box_summary_to_read",
    "close_savings_box",
    "create_booking",
    "create_box",
    "delete_booking",
    "get_box_detail",
    "get_box_list_projection",
    "get_box_or_404",
    "list_boxes",
    "reopen_savings_box",
    "savings_box_to_detail",
    "savings_box_to_read",
    "update_booking",
    "update_box",
    "update_term_statuses",
]
