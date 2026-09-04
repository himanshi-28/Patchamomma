from datetime import UTC, datetime

import pytest

from app.cost_controls import COST_CONTROLS_SCHEMA_VERSION
from scripts.set_cost_controls import confirm_and_apply_change

CURRENT = {
    "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
    "geminiProjectDailyAllowance": 20,
    "maintenanceMode": False,
    "updatedAt": datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
}


def test_operator_script_prints_project_and_change_then_requires_exact_confirmation() -> None:
    output: list[str] = []
    writes: list[dict[str, object]] = []

    changed = confirm_and_apply_change(
        project_id="patchamomma-2026-505415",
        current=CURRENT,
        allowance=0,
        maintenance_mode=None,
        input_fn=lambda _prompt: "no",
        output_fn=output.append,
        write_fn=writes.append,
        server_timestamp="SERVER_TIMESTAMP",
    )

    assert changed is False
    assert writes == []
    rendered = "\n".join(output)
    assert "patchamomma-2026-505415" in rendered
    assert "geminiProjectDailyAllowance: 20 -> 0" in rendered


def test_confirmed_operator_change_writes_the_complete_versioned_document() -> None:
    writes: list[dict[str, object]] = []

    changed = confirm_and_apply_change(
        project_id="patchamomma-2026-505415",
        current=CURRENT,
        allowance=0,
        maintenance_mode=True,
        input_fn=lambda _prompt: "CONFIRM patchamomma-2026-505415",
        output_fn=lambda _message: None,
        write_fn=writes.append,
        server_timestamp="SERVER_TIMESTAMP",
    )

    assert changed is True
    assert writes == [
        {
            "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
            "geminiProjectDailyAllowance": 0,
            "maintenanceMode": True,
            "updatedAt": "SERVER_TIMESTAMP",
        }
    ]


def test_operator_script_rejects_out_of_range_allowance_before_confirmation() -> None:
    with pytest.raises(ValueError, match="0 through 20"):
        confirm_and_apply_change(
            project_id="patchamomma-2026-505415",
            current=CURRENT,
            allowance=21,
            maintenance_mode=None,
            input_fn=lambda _prompt: "CONFIRM patchamomma-2026-505415",
            output_fn=lambda _message: None,
            write_fn=lambda _document: None,
            server_timestamp="SERVER_TIMESTAMP",
        )

def test_initial_document_creation_requires_both_explicit_values() -> None:
    with pytest.raises(ValueError, match="both values"):
        confirm_and_apply_change(
            project_id="patchamomma-2026-505415",
            current=None,
            allowance=20,
            maintenance_mode=None,
            input_fn=lambda _prompt: "CONFIRM patchamomma-2026-505415",
            output_fn=lambda _message: None,
            write_fn=lambda _document: None,
            server_timestamp="SERVER_TIMESTAMP",
        )
