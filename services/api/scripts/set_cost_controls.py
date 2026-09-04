import argparse
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import firebase_admin
from firebase_admin import firestore

from app.cost_controls import (
    COST_CONTROLS_COLLECTION,
    COST_CONTROLS_DOCUMENT,
    COST_CONTROLS_SCHEMA_VERSION,
    GEMINI_DEPLOYMENT_DAILY_MAXIMUM,
    CostControlState,
)


def _parse_boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("Use exactly true or false")


def confirm_and_apply_change(
    *,
    project_id: str,
    current: Mapping[str, object] | None,
    allowance: int | None,
    maintenance_mode: bool | None,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    write_fn: Callable[[dict[str, object]], None],
    server_timestamp: object,
) -> bool:
    if not project_id.strip():
        raise ValueError("An explicit active project is required")
    if allowance is not None and not 0 <= allowance <= GEMINI_DEPLOYMENT_DAILY_MAXIMUM:
        raise ValueError("geminiProjectDailyAllowance must be from 0 through 20")
    if current is None:
        if allowance is None or maintenance_mode is None:
            raise ValueError("Initial document creation requires both values")
        current_allowance: int | None = None
        current_maintenance: bool | None = None
    else:
        state = CostControlState.model_validate(current)
        current_allowance = state.gemini_project_daily_allowance
        current_maintenance = state.maintenance_mode
        allowance = current_allowance if allowance is None else allowance
        maintenance_mode = current_maintenance if maintenance_mode is None else maintenance_mode

    assert allowance is not None
    assert maintenance_mode is not None
    if current is not None and (
        allowance == current_allowance and maintenance_mode == current_maintenance
    ):
        raise ValueError("Requested values do not change the active document")

    output_fn(f"Active project: {project_id}")
    output_fn(
        "geminiProjectDailyAllowance: "
        f"{current_allowance if current_allowance is not None else '<missing>'} -> {allowance}"
    )
    output_fn(
        "maintenanceMode: "
        f"{current_maintenance if current_maintenance is not None else '<missing>'} "
        f"-> {maintenance_mode}"
    )
    expected = f"CONFIRM {project_id}"
    if input_fn(f"Type '{expected}' to write the control document: ") != expected:
        output_fn("No change written.")
        return False

    document: dict[str, object] = {
        "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
        "geminiProjectDailyAllowance": allowance,
        "maintenanceMode": maintenance_mode,
        "updatedAt": server_timestamp,
    }
    write_fn(document)
    output_fn("Cost-control document updated.")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Confirm and update SakhiCircle production cost controls.",
    )
    parser.add_argument("--project", required=True, help="Exact active Firebase project ID")
    parser.add_argument(
        "--gemini-project-daily-allowance",
        type=int,
        choices=range(GEMINI_DEPLOYMENT_DAILY_MAXIMUM + 1),
    )
    parser.add_argument("--maintenance-mode", type=_parse_boolean)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.gemini_project_daily_allowance is None and args.maintenance_mode is None:
        raise SystemExit("Specify at least one requested control change")

    app = firebase_admin.initialize_app(options={"projectId": args.project})
    client = firestore.client(app=app)
    reference: Any = client.collection(COST_CONTROLS_COLLECTION).document(
        COST_CONTROLS_DOCUMENT
    )
    snapshot = reference.get()
    current = snapshot.to_dict() if snapshot.exists else None
    changed = confirm_and_apply_change(
        project_id=args.project,
        current=current,
        allowance=args.gemini_project_daily_allowance,
        maintenance_mode=args.maintenance_mode,
        input_fn=input,
        output_fn=print,
        write_fn=reference.set,
        server_timestamp=firestore.SERVER_TIMESTAMP,
    )
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
