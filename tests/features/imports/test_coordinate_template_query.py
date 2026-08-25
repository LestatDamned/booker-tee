from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.mapping.coordinate_dto import CoordinateMappingSpec
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.models import ImportMappingTemplate


@pytest.mark.asyncio
async def test_coordinate_template_query_filters_workspace_and_kind_before_limit() -> None:
    statements = []

    class Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class Session:
        async def execute(self, statement):
            statements.append(statement)
            return Result()

    await MappingRepository(cast(AsyncSession, Session())).list_coordinate_templates(
        workspace_id=uuid4()
    )
    sql = str(statements[0].compile(dialect=postgresql.dialect()))

    assert "workspace_id" in sql
    assert "column_mapping_json ->>" in sql
    assert sql.index("column_mapping_json ->>") < sql.index("LIMIT")


@pytest.mark.asyncio
async def test_coordinate_template_create_stores_typed_discriminator() -> None:
    added = []

    class Session:
        def add(self, model):
            model.id = uuid4()
            added.append(model)

        async def flush(self):
            return None

    workspace_id = uuid4()
    snapshot = await MappingRepository(cast(AsyncSession, Session())).create_coordinate_template(
        workspace_id=workspace_id,
        name="Bank PDF",
        spec=_spec(),
    )

    assert snapshot.name == "Bank PDF"
    assert added[0].workspace_id == workspace_id
    assert added[0].column_mapping_json["kind"] == "visual_coordinates"
    assert added[0].column_mapping_json["version"] == 1


@pytest.mark.asyncio
async def test_coordinate_template_malformed_version_is_controlled() -> None:
    template = ImportMappingTemplate(
        id=uuid4(),
        workspace_id=uuid4(),
        name="Future",
        default_currency="RUB",
        column_mapping_json={"kind": "visual_coordinates", "version": 2, "spec": {}},
    )

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [template]

    class Session:
        async def execute(self, _statement):
            return Result()

    with pytest.raises(ValueError, match="Unsupported visual coordinate template version"):
        await MappingRepository(cast(AsyncSession, Session())).list_coordinate_templates(
            workspace_id=template.workspace_id
        )


@pytest.mark.asyncio
async def test_visual_template_is_excluded_from_legacy_autoapply() -> None:
    workspace_id = uuid4()
    visual = ImportMappingTemplate(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Visual",
        bank_name="Bank",
        statement_type="card",
        default_currency="RUB",
        column_mapping_json={
            "kind": "visual_coordinates",
            "version": 1,
            "spec": _spec().model_dump(mode="json"),
        },
    )
    legacy = ImportMappingTemplate(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Columns",
        bank_name="Bank",
        statement_type="card",
        default_currency="RUB",
        column_mapping_json={
            "operation_date_column": 0,
            "description_column": 1,
            "amount_column": 2,
            "default_currency": "RUB",
        },
    )

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [visual, legacy]

    class Session:
        async def execute(self, _statement):
            return Result()

    snapshots = await MappingRepository(cast(AsyncSession, Session())).list_matching_templates(
        workspace_id=workspace_id,
        bank_name="Bank",
        statement_type="card",
    )

    assert [snapshot.id for snapshot in snapshots] == [legacy.id]


def _spec() -> CoordinateMappingSpec:
    return CoordinateMappingSpec.model_validate(
        {
            "defaultCurrency": "RUB",
            "layouts": {
                "first": {
                    "pageAspectRatio": 0.75,
                    "transactionTop": 0.1,
                    "transactionBottom": 0.9,
                    "sampleRow": {"x0": 0.05, "y0": 0.2, "x1": 0.95, "y1": 0.3},
                    "fields": {
                        "operation_date": {"x0": 0.05, "y0": 0.2, "x1": 0.2, "y1": 0.3},
                        "description": {"x0": 0.25, "y0": 0.2, "x1": 0.65, "y1": 0.3},
                        "amount": {"x0": 0.75, "y0": 0.2, "x1": 0.95, "y1": 0.3},
                    },
                }
            },
        }
    )
