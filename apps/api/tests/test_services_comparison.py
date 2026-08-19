from unittest.mock import MagicMock, patch

from app.services.comparison import compare_audit_periods

_FROM_ID = "period-2025"
_TO_ID = "period-2026"


def test_compare_audit_periods_diffs_controls_by_control_code() -> None:
    fake_client = MagicMock()
    with (
        patch("app.services.comparison.audit_periods_repo") as fake_periods_repo,
        patch("app.services.comparison.report_entities_repo") as fake_entities_repo,
    ):
        fake_periods_repo.get_audit_period.side_effect = lambda _client, *, audit_period_id: {
            _FROM_ID: {"id": _FROM_ID, "name": "FY2025"},
            _TO_ID: {"id": _TO_ID, "name": "FY2026"},
        }[audit_period_id]

        def list_soc_controls(_client: object, *, audit_period_id: str) -> list[dict[str, str]]:
            if audit_period_id == _FROM_ID:
                return [
                    {"control_code": "CC6.1", "description": "Old wording"},
                    {"control_code": "CC7.1", "description": "Stable control"},
                    {"control_code": "CC8.1", "description": "Removed next year"},
                ]
            return [
                {"control_code": "CC6.1", "description": "New wording"},
                {"control_code": "CC7.1", "description": "Stable control"},
                {"control_code": "CC9.1", "description": "Brand new control"},
            ]

        fake_entities_repo.list_soc_controls.side_effect = list_soc_controls
        fake_entities_repo.list_cuecs.return_value = []
        fake_entities_repo.list_exceptions.return_value = []
        fake_entities_repo.list_subservice_organizations.return_value = []

        result = compare_audit_periods(
            fake_client, from_audit_period_id=_FROM_ID, to_audit_period_id=_TO_ID
        )

        assert result.from_audit_period_name == "FY2025"
        assert result.to_audit_period_name == "FY2026"
        assert [c["control_code"] for c in result.controls.added] == ["CC9.1"]
        assert [c["control_code"] for c in result.controls.removed] == ["CC8.1"]
        assert len(result.controls.changed) == 1
        assert result.controls.changed[0].control_code == "CC6.1"
        assert result.controls.changed[0].description_from == "Old wording"
        assert result.controls.changed[0].description_to == "New wording"
        assert result.controls.unchanged_count == 1


def test_compare_audit_periods_excludes_controls_with_no_code() -> None:
    fake_client = MagicMock()
    with (
        patch("app.services.comparison.audit_periods_repo") as fake_periods_repo,
        patch("app.services.comparison.report_entities_repo") as fake_entities_repo,
    ):
        fake_periods_repo.get_audit_period.return_value = {"id": _FROM_ID, "name": "FY2025"}
        fake_entities_repo.list_soc_controls.return_value = [
            {"control_code": None, "description": "Uncoded control"}
        ]
        fake_entities_repo.list_cuecs.return_value = []
        fake_entities_repo.list_exceptions.return_value = []
        fake_entities_repo.list_subservice_organizations.return_value = []

        result = compare_audit_periods(
            fake_client, from_audit_period_id=_FROM_ID, to_audit_period_id=_FROM_ID
        )

        assert result.controls.added == []
        assert result.controls.removed == []
        assert result.controls.changed == []
        assert result.controls.unchanged_count == 0
