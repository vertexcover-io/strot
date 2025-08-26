import os
import tempfile
from pathlib import Path
from typing import Any

import httpx
from pyairtable import Api, Table

from strot.logging import LoggerType, get_logger

from ..settings import env_settings
from . import schema


class AirtableClient:
    """Airtable client with auto-creating table properties."""

    def __init__(self, logger: LoggerType | None = None):
        self._logger = logger or get_logger()
        self._api = Api(env_settings.AIRTABLE_TOKEN)

        self._tables: dict[str, Table] = {}

    async def table_exists(self, name: str) -> bool:
        self._logger.info("table-exists", table=name, status="pending")

        try:
            async with httpx.AsyncClient(
                base_url=f"https://api.airtable.com/v0/meta/bases/{env_settings.AIRTABLE_BASE_ID}"
            ) as client:
                headers = {"Authorization": f"Bearer {env_settings.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

                response = await client.get("/tables", headers=headers)
                response.raise_for_status()

                exists = name in {table["name"] for table in response.json()["tables"]}

                self._logger.info("table-exists", table=name, status="completed", exists=exists)
                return exists

        except Exception as e:
            self._logger.info("table-exists", table=name, status="failed", reason=e)
            raise

    async def create_table(self, name: str, fields: list[schema.AirtableField]) -> str:
        """Create table and return table ID."""
        self._logger.info("create-table", table=name, status="pending")

        try:
            async with httpx.AsyncClient(
                base_url=f"https://api.airtable.com/v0/meta/bases/{env_settings.AIRTABLE_BASE_ID}"
            ) as client:
                headers = {"Authorization": f"Bearer {env_settings.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

                response = await client.post("/tables", headers=headers, json={"name": name, "fields": fields})
                response.raise_for_status()

                table_id = response.json()["id"]

                self._logger.info("create-table", table=name, status="success", table_id=table_id)
                return table_id

        except Exception as e:
            self._logger.info("create-table", table=name, status="failed", reason=e)
            raise

    def get_table(self, table_name: str) -> Table:
        """Get table instance."""
        if table_name not in self._tables:
            self._tables[table_name] = self._api.table(env_settings.AIRTABLE_BASE_ID, table_name)
        return self._tables[table_name]

    async def get_metrics_table(self) -> Table:
        table_name = env_settings.AIRTABLE_METRICS_TABLE

        if not (await self.table_exists(table_name)):
            analysis_steps_table_id = (await self.get_analysis_steps_table()).id
            await self.create_table(
                table_name,
                schema.EvaluationMetricsAirtableSchema.fields(analysis_steps_table_id),
            )

        return self.get_table(table_name)

    async def get_analysis_steps_table(self) -> Table:
        """Get or create analysis steps table."""
        table_name = env_settings.AIRTABLE_ANALYSIS_STEPS_TABLE

        if not (await self.table_exists(table_name)):
            await self.create_table(
                table_name,
                schema.AnalysisStepsAirtableSchema.fields(),
            )

        return self.get_table(table_name)

    async def get_request_detection_table(self) -> Table:
        """Get or create request detection evaluation table."""
        table_name = env_settings.AIRTABLE_REQUEST_DETECTION_TABLE

        if not (await self.table_exists(table_name)):
            await self.create_table(
                table_name,
                schema.RequestDetectionAirtableSchema.fields(),
            )

        return self.get_table(table_name)

    async def get_pagination_detection_table(self) -> Table:
        """Get or create pagination detection evaluation table."""
        table_name = env_settings.AIRTABLE_PAGINATION_DETECTION_TABLE

        if not (await self.table_exists(table_name)):
            await self.create_table(
                table_name,
                schema.PaginationDetectionAirtableSchema.fields(),
            )

        return self.get_table(table_name)

    async def get_code_generation_table(self) -> Table:
        """Get or create code generation evaluation table."""
        table_name = env_settings.AIRTABLE_CODE_GENERATION_TABLE

        if not (await self.table_exists(table_name)):
            await self.create_table(
                table_name,
                schema.CodeGenerationAirtableSchema.fields(),
            )

        return self.get_table(table_name)

    def upload_attachment(
        self,
        table: Table,
        primary_field_kv: tuple[str, Any],
        attachment_field: str,
        attachment_data: bytes,
        attachment_name: str,
    ) -> schema.Attachment | None:
        """Upload base64 image data to Airtable as attachment using direct upload."""

        self._logger.info("upload-attachment", name=attachment_name, status="pending")
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(attachment_name).suffix) as temp_file:
                temp_file.write(attachment_data)
                temp_file_path = temp_file.name

            record_id = None
            try:
                record_id = table.create({primary_field_kv[0]: primary_field_kv[1]})["id"]
                with open(temp_file_path, "rb") as f:
                    attachment = table.upload_attachment(record_id, attachment_field, attachment_name, f.read())

                field_key = next(iter(attachment["fields"].keys()))
                attachment_info = attachment["fields"][field_key][0]

                self._logger.info(
                    "upload-attachment", name=attachment_name, status="completed", url=attachment_info["url"]
                )
                return {"url": attachment_info["url"]}

            finally:
                try:
                    os.unlink(temp_file_path)
                    if record_id:
                        table.delete(record_id)
                except Exception:  # noqa: S110
                    pass

        except Exception as e:
            self._logger.info("upload-attachment", name=attachment_name, status="failed", reason=e)
            return None
