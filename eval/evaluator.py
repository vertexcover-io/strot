import asyncio
import base64
import json
import os
import tempfile
from typing import Any
from uuid import uuid4

from pyairtable import Api, Table
from pydantic import BaseModel, Field

from strot.logging import LoggerType, get_logger, setup_logging

from .client import StrotClient
from .log_parser import parse_jsonl_logs
from .settings import settings

setup_logging()


class _CommonInput(BaseModel):
    expected_source_url: str = Field(..., description="Expected source URL")
    expected_pagination_keys: list[str] = Field(default_factory=list, description="Expected pagination keys")
    expected_entity_count: int = Field(0, description="Expected entity count")


class NewJobInput(_CommonInput):
    site_url: str = Field(..., description="Site URL")
    label: str = Field(..., description="Label")


class ExistingJobInput(_CommonInput):
    job_id: str = Field(..., description="Job ID")


class Evaluator:
    """Evaluator class that handles job evaluation and Airtable data writing."""

    def __init__(self, logger: LoggerType | None = None):
        self._logger = logger or get_logger()
        self._client = StrotClient(logger=self._logger)

        self._api = Api(settings.AIRTABLE_TOKEN)
        self._base_id = settings.AIRTABLE_BASE_ID
        self._overview_table = self._api.table(self._base_id, settings.AIRTABLE_OVERVIEW_TABLE)
        self._analysis_steps_table = self._api.table(self._base_id, settings.AIRTABLE_ANALYSIS_STEPS_TABLE)

    def _upload_base64_image(
        self,
        table: Table,
        from_field_name_value_tuple: tuple[str, Any],
        attachment_field_name: str,
        base64_data: str,
        filename: str,
    ) -> dict[str, Any] | None:
        """Upload base64 image data to Airtable as attachment using direct upload."""
        self._logger.info("upload-image", filename=filename, status="pending")
        try:
            image_data = base64.b64decode(base64_data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name

            record_id = None
            try:
                record_id = table.create({from_field_name_value_tuple[0]: from_field_name_value_tuple[1]})["id"]
                with open(temp_file_path, "rb") as f:
                    attachment = table.upload_attachment(record_id, attachment_field_name, filename, f.read())

                field_key = next(iter(attachment["fields"].keys()))
                attachment_info = attachment["fields"][field_key][0]

                self._logger.info("upload-image", filename=filename, status="completed", url=attachment_info["url"])
                return {"url": attachment_info["url"]}

            finally:
                try:
                    os.unlink(temp_file_path)
                    if record_id:
                        self._analysis_steps_table.delete(record_id)
                except Exception:  # noqa: S110
                    pass

        except Exception as e:
            self._logger.info("upload-image", status="failed", filename=filename, reason=e)
            return None

    def _prepare_analysis_step_data_entries(self, job_id: str) -> list[dict[str, Any]]:
        """Prepare analysis step data for Airtable."""
        self._logger.info("prepare-analysis-step-data", job_id=job_id, status="pending")
        report_data = parse_jsonl_logs(self._client.fetch_logs(job_id))

        entries = []

        index = 0
        for step in report_data.analysis_steps:
            # Determine step execution outcome
            if step.status == "failed" and step.reason:
                outcome = f"No request match, reason: {step.reason}"
            elif step.status == "success":
                outcome = f"Request matched: {step.method} {step.url}"
            else:
                outcome = f"Status: {step.status or 'unknown'}"

            # Process each sub-event that has a step
            for event in step.sub_events:
                if not event.step or not event.context:
                    continue

                attachment = self._upload_base64_image(
                    self._analysis_steps_table,
                    ("job_id", job_id),
                    "context_before_step_execution",
                    event.context,
                    f"job_{job_id}_step_{event.step}.png",
                )
                entries.append({
                    "job_id": job_id,
                    "index": index,
                    "step": event.step,
                    "context_before_step_execution": [attachment],
                    "step_execution_outcome": outcome,
                })
                index += 1

        self._logger.info("prepare-analysis-step-data", job_id=job_id, status="completed", count=len(entries))
        return entries

    def _get_existing_analysis_step_ids(self, job_id: str) -> list[str]:
        """Get existing analysis step record IDs for this job in creation order."""
        self._logger.info("get-analysis-step-records", job_id=job_id, status="pending")
        try:
            records = self._analysis_steps_table.all(
                formula=f"{{job_id}} = '{job_id}'",
                sort=["index"],  # Sort by index for proper order
            )
            record_ids = [record["id"] for record in records]
            self._logger.info("get-analysis-step-records", job_id=job_id, status="completed", count=len(record_ids))
        except Exception as e:
            self._logger.info("get-analysis-step-records", job_id=job_id, status="failed", reason=str(e))
            return []
        else:
            return record_ids

    def _create_analysis_steps_records(self, entries: list[dict[str, Any]]) -> list[str]:
        """Create analysis steps records in Airtable with image uploads."""
        self._logger.info("create-analysis-step-records", status="pending", count=len(entries))

        if not entries:
            self._logger.info("create-analysis-step-records", status="failed", reason="No steps data")
            return []

        record_ids = []
        batch_size = 100

        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            try:
                records = self._analysis_steps_table.batch_create(batch)
                record_ids.extend([record["id"] for record in records])
                self._logger.info(
                    "create-analysis-step-records", size=i // batch_size + 1, status="completed", records=len(records)
                )
            except Exception as e:
                self._logger.info("create-analysis-step-records", size=i // batch_size + 1, status="failed", reason=e)
                for individual_record in batch:
                    try:
                        record = self._analysis_steps_table.create(individual_record)
                        record_ids.append(record["id"])
                        self._logger.info(
                            "create-analysis-step-records", size=1, status="completed", record_id=record["id"]
                        )
                    except Exception as e:
                        self._logger.info("create-analysis-step-records", size=1, status="failed", reason=e)

        self._logger.info("create-analysis-step-records", status="completed", total_records_created=len(record_ids))
        return record_ids

    async def _prepare_overview_data(
        self,
        job_response: dict[str, Any],
        expected_source_url: str,
        expected_pagination_keys: list[str],
        expected_entity_count: int,
    ) -> dict[str, Any]:
        """Prepare overview data for Airtable."""
        job_id = job_response["job_id"]
        self._logger.info("prepare-overview-data", job_id=job_id, status="pending")
        overview_data = {
            "target_site": job_response.get("url", ""),
            "label": job_response.get("label", ""),
            "source_url_expected": expected_source_url,
            "pagination_keys_expected": expected_pagination_keys,
            "entity_count_expected": expected_entity_count,
        }

        source = job_response.get("source")
        if not source:
            overview_data.update({
                "source_url_actual": "",
                "source_url_matching": "no",
                "pagination_keys_actual": [],
                "pagination_keys_matching": "no",
                "entity_count_actual": 0,
                "entity_count_difference": 100.00,
            })

        else:
            source_url_actual = source["request"]["url"]

            pagination_strategy = source.get("pagination_strategy") or {}
            pagination_keys_actual = [v for k, v in pagination_strategy.items() if k.endswith("_key") and v]

            try:
                entities = await self._client.fetch_data(job_id, limit=expected_entity_count, offset=0)
                entity_count_actual = len(entities)
            except Exception:
                entity_count_actual = 0

            source_url_matching = "no"
            if expected_source_url and source_url_actual:
                source_url_matching = "yes" if expected_source_url.strip() == source_url_actual.strip() else "no"

            self._logger.info(
                "prepare-overview-data",
                job_id=job_id,
                action="compare-urls",
                expected=expected_source_url,
                actual=source_url_actual,
                match=source_url_matching,
            )

            pagination_keys_matching = "no"
            if expected_pagination_keys and pagination_keys_actual:
                expected_set = set(expected_pagination_keys)
                actual_set = set(pagination_keys_actual)
                pagination_keys_matching = "yes" if expected_set == actual_set else "no"

            self._logger.info(
                "prepare-overview-data",
                job_id=job_id,
                action="compare-pagination-keys",
                expected=expected_pagination_keys,
                actual=pagination_keys_actual,
                match=pagination_keys_matching,
            )

            if expected_entity_count == 0:
                entity_count_difference = 100.00 if entity_count_actual > 0 else 0.00
            else:
                difference = abs(expected_entity_count - entity_count_actual)
                entity_count_difference = (difference / expected_entity_count) * 100
                entity_count_difference = round(entity_count_difference, 2)

            self._logger.info(
                "prepare-overview-data",
                job_id=job_id,
                action="calculate-entity-difference",
                expected=expected_entity_count,
                actual=entity_count_actual,
                difference_percent=entity_count_difference,
            )

            overview_data.update({
                "source_url_actual": source_url_actual,
                "source_url_matching": source_url_matching,
                "pagination_keys_actual": pagination_keys_actual,
                "pagination_keys_matching": pagination_keys_matching,
                "entity_count_actual": entity_count_actual,
                "entity_count_difference": entity_count_difference,
            })

        self._logger.info("prepare-overview-data", job_id=job_id, status="completed", **overview_data)
        return overview_data

    def _create_overview_record(self, overview_data: dict[str, Any], analysis_steps_record_ids: list[str]) -> str:
        """Create overview record in Airtable."""
        run_id = str(uuid4())
        self._logger.info(
            "create-overview-record",
            run_id=run_id,
            target_site=overview_data["target_site"],
            label=overview_data["label"],
            status="pending",
        )
        fields = {
            **overview_data,
            "pagination_keys_expected": json.dumps(overview_data["pagination_keys_expected"]),
            "pagination_keys_actual": json.dumps(overview_data["pagination_keys_actual"]),
            "run_id": run_id,
        }

        if analysis_steps_record_ids:
            fields["analysis_steps"] = analysis_steps_record_ids

        record = self._overview_table.create(fields)
        self._logger.info(
            "create-overview-record",
            run_id=run_id,
            target_site=overview_data["target_site"],
            label=overview_data["label"],
            status="completed",
            record_id=record["id"],
        )
        return record["id"]

    async def evaluate(self, input: NewJobInput | ExistingJobInput) -> None:
        """Evaluate the analysis job."""
        if isinstance(input, NewJobInput):
            job_id = await self._client.create_job(input.site_url, input.label)
        else:
            job_id = input.job_id

        self._logger.info("evaluate", job_id=job_id, status="pending")
        while True:
            try:
                job_response = await self._client.get_job(job_id)
            except Exception:
                return
            if job_response.get("status") == "pending":
                await asyncio.sleep(7.5)
            else:
                break

        try:
            overview_data = await self._prepare_overview_data(
                job_response,
                input.expected_source_url,
                input.expected_pagination_keys,
                input.expected_entity_count,
            )

            analysis_step_record_ids = self._get_existing_analysis_step_ids(job_id)
            if not analysis_step_record_ids:
                analysis_step_record_ids = self._create_analysis_steps_records(
                    self._prepare_analysis_step_data_entries(job_id)
                )

            self._create_overview_record(overview_data, analysis_step_record_ids)
        except Exception as e:
            self._logger.info("evaluate", job_id=job_id, status="failed", reason=e)
            raise

        self._logger.info(
            "evaluate", job_id=job_id, status="completed", airtable_url=f"https://airtable.com/{self._base_id}"
        )
