"""
Prompt 10E Part 7.8 — one-off re-route of existing test orders to lab rooms.

For every non-completed, non-cancelled order (status not COMPLETED / CANCELLED and its invoice
line not cancelled):
  1. room = the test's room (tests.lab_section, else the mapping in core/lab_sections.py);
     when a NON-imaging test maps to no room, the room named by the order's existing
     assigned_destination is used (e.g. a front-desk assignment to "Microbiology Lab 105", or a
     legacy destination id such as "6" resolved through test_destinations). Imaging tests that
     map to no room (e.g. X-ray) stay without a room; doctor-routed ones remain in the doctor
     queue.
  2. ASSIGNED / UNASSIGNED orders are re-evaluated: ASSIGNED when the room has an active
     LAB_TECH, else UNASSIGNED. Other in-flight statuses (IN_PROGRESS, AWAITING_DOCTOR,
     REJECTED, ...) keep their status; only the room is recorded.
  3. assigned_destination is set to the room name (never an id). assigned_to_id is kept as the
     record of who acted; it is no longer used for visibility.
One audit_logs row (ORDER_REROUTED_TO_ROOM) per changed order. Completed / cancelled orders are
left untouched. Dry run by default; --apply writes.

Usage (from the repository root):
    python -m backend.scripts.reroute_orders_to_rooms            # dry run
    python -m backend.scripts.reroute_orders_to_rooms --apply    # write
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select  # noqa: E402

from backend.app.core.database import SessionLocal  # noqa: E402
from backend.app.core.lab_sections import lab_section_destination, section_for_test  # noqa: E402
from backend.app.core.samples import is_imaging_test  # noqa: E402
from backend.app.models.invoice import InvoiceLine  # noqa: E402
from backend.app.models.test_order import TestOrder  # noqa: E402
from backend.app.services.audit_service import log_audit_event  # noqa: E402
from backend.app.services.routing_service import resolve_room, room_has_active_technician  # noqa: E402

SKIP_STATUSES = ("COMPLETED", "CANCELLED")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Write the changes (default: dry run)")
    args = ap.parse_args()

    db = SessionLocal()
    changed = 0
    by_room = Counter()
    status_moves = Counter()
    try:
        orders = db.execute(
            select(TestOrder).join(TestOrder.invoice_line).where(
                TestOrder.status.not_in(SKIP_STATUSES), InvoiceLine.status != "CANCELLED"
            ).order_by(TestOrder.id)
        ).scalars().all()
        for o in orders:
            test = o.invoice_line.test
            room = section_for_test(test)
            if not room and not is_imaging_test(test, o):
                room = resolve_room(db, o.tenant_id, o.assigned_destination)
            new_status = o.status
            if o.status in ("ASSIGNED", "UNASSIGNED"):
                new_status = "ASSIGNED" if (room and room_has_active_technician(db, o.tenant_id, room)) else "UNASSIGNED"
            new_dest = lab_section_destination(room) if room else o.assigned_destination
            if new_dest is not None and str(new_dest).strip().isdigit():
                new_dest = None  # never keep a raw destination id
            if (o.lab_section, o.status, o.assigned_destination) == (room, new_status, new_dest):
                by_room[room or "(no room)"] += 1
                continue
            before = f"room={o.lab_section}, status={o.status}, destination={o.assigned_destination}"
            after = f"room={room}, status={new_status}, destination={new_dest}"
            print(f"#{o.id:<5} {o.invoice_line.test_code_snapshot:<12} {before}  ->  {after}")
            changed += 1
            by_room[room or "(no room)"] += 1
            status_moves[(o.status, new_status)] += 1
            if args.apply:
                o.lab_section = room
                o.status = new_status
                o.assigned_destination = new_dest
                log_audit_event(
                    db=db, tenant_id=o.tenant_id, action="ORDER_REROUTED_TO_ROOM", entity_type="TEST_ORDER",
                    entity_id=o.id, acting_role="SYSTEM", actor_id=None,
                    before_value=before, after_value=after + " (Prompt 10E one-off re-route)",
                )
        print("-" * 72)
        print(f"Orders considered (non-completed, non-cancelled): {len(orders)}")
        print(f"Orders changed: {changed}  ({'APPLIED' if args.apply else 'DRY RUN - nothing written'})")
        print("Per room after re-route (considered orders): " + ", ".join(f"{k}={v}" for k, v in sorted(by_room.items())))
        print("Status moves: " + (", ".join(f"{a}->{b}: {n}" for (a, b), n in sorted(status_moves.items())) or "none"))
        if args.apply:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
