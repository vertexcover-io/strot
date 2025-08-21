import asyncio
import base64
import json
import os
import tempfile
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx
from pyairtable import Api, Table
from pyairtable.api.types import RecordDict

from strot.logging import LoggerType, LogLevel, get_logger, setup_logging

from .client import StrotClient
from .log_parser import parse_jsonl_logs
from .settings import AnalysisStepsAirtableSchema, EvaluationMetricsAirtableSchema, env_settings
from .types import ExistingJobInput, NewJobInput

setup_logging(overrides={"httpx": LogLevel.WARNING})


class Evaluator:
    def __init__(self, logger: LoggerType | None = None):
        self._logger = logger or get_logger()
        self._client = StrotClient(logger=self._logger)

        self._api = Api(env_settings.AIRTABLE_TOKEN)

        self._metrics_table = None
        self._analysis_steps_table = None

    async def _ensure_tables_exist(self) -> None:
        """Ensure required Airtable tables exist, create them if they don't."""

        self._logger.info("ensure-tables-exist", status="checking")

        try:
            async with httpx.AsyncClient(
                base_url=f"https://api.airtable.com/v0/meta/bases/{env_settings.AIRTABLE_BASE_ID}"
            ) as client:
                headers = {"Authorization": f"Bearer {env_settings.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

                response = await client.get("/tables", headers=headers)
                existing_tables = {table["name"]: table["id"] for table in response.json()["tables"]}

                analysis_steps_table_id = None
                analysis_steps_table_name = env_settings.AIRTABLE_ANALYSIS_STEPS_TABLE
                if analysis_steps_table_name not in existing_tables:
                    self._logger.info("ensure-tables-exist", table=analysis_steps_table_name, status="creating")

                    analysis_steps_schema = {
                        "name": analysis_steps_table_name,
                        "fields": [
                            AnalysisStepsAirtableSchema.job_id,
                            AnalysisStepsAirtableSchema.index,
                            AnalysisStepsAirtableSchema.step,
                            AnalysisStepsAirtableSchema.screenshot_before_step_execution,
                            AnalysisStepsAirtableSchema.step_execution_outcome,
                        ],
                    }

                    response = await client.post("/tables", headers=headers, json=analysis_steps_schema)
                    analysis_steps_table_id = response.json()["id"]
                    self._logger.info(
                        "ensure-tables-exist",
                        table=analysis_steps_table_name,
                        status="created",
                        table_id=analysis_steps_table_id,
                    )
                else:
                    analysis_steps_table_id = existing_tables[analysis_steps_table_name]
                    self._logger.info("ensure-tables-exist", table=analysis_steps_table_name, status="exists")

                metrics_table_name = env_settings.AIRTABLE_METRICS_TABLE
                if metrics_table_name not in existing_tables:
                    self._logger.info("ensure-tables-exist", table=metrics_table_name, status="creating")

                    metrics_schema = {
                        "name": metrics_table_name,
                        "fields": [
                            EvaluationMetricsAirtableSchema.run_id,
                            EvaluationMetricsAirtableSchema.initiated_at,
                            EvaluationMetricsAirtableSchema.completed_at,
                            EvaluationMetricsAirtableSchema.target_site,
                            EvaluationMetricsAirtableSchema.label,
                            EvaluationMetricsAirtableSchema.source_expected,
                            EvaluationMetricsAirtableSchema.source_actual,
                            EvaluationMetricsAirtableSchema.source_matching,
                            EvaluationMetricsAirtableSchema.pagination_keys_expected,
                            EvaluationMetricsAirtableSchema.pagination_keys_actual,
                            EvaluationMetricsAirtableSchema.pagination_keys_matching,
                            EvaluationMetricsAirtableSchema.entity_count_expected,
                            EvaluationMetricsAirtableSchema.entity_count_actual,
                            EvaluationMetricsAirtableSchema.entity_count_difference,
                            EvaluationMetricsAirtableSchema.analysis_steps
                            | {"options": {"linkedTableId": analysis_steps_table_id}},
                            EvaluationMetricsAirtableSchema.comment,
                        ],
                    }

                    response = await client.post("/tables", headers=headers, json=metrics_schema)
                    metrics_table_id = response.json()["id"]
                    self._logger.info(
                        "ensure-tables-exist", table=metrics_table_name, status="created", table_id=metrics_table_id
                    )
                else:
                    metrics_table_id = existing_tables[metrics_table_name]
                    self._logger.info("ensure-tables-exist", table=metrics_table_name, status="exists")

                self._logger.info("ensure-tables-exist", status="completed")

        except Exception as e:
            self._logger.info("ensure-tables-exist", status="failed", reason=f"Table creation failed: {e!s}")
            raise

    def _upload_base64_image(
        self,
        table: Table,
        primary_field: tuple[str, Any],
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
                record_id = table.create({primary_field[0]: primary_field[1]})["id"]
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
                        table.delete(record_id)
                except Exception:  # noqa: S110
                    pass

        except Exception as e:
            self._logger.info("upload-image", status="failed", filename=filename, reason=e)
            return None

    def _prepare_analysis_steps(self, job_id: str) -> list[dict[str, Any]]:
        """Prepare analysis steps for Airtable."""

        self._logger.info("prepare-analysis-steps", job_id=job_id, status="pending")
        report_data = parse_jsonl_logs(self._client.fetch_logs(job_id))

        entries, index = [], 0
        for step in report_data.analysis_steps:
            # Determine step execution outcome
            if step.status == "failed" and step.reason:
                outcome = f"No request match, reason: {step.reason}"
            elif step.status == "success":
                outcome = f"Request matched: {step.method} {step.url}"
            else:
                outcome = f"Status: {step.status or "unknown"}"

            # Process each sub-event that has a step
            for event in step.sub_events:
                if not event.step or not event.context:
                    continue

                attachment = self._upload_base64_image(
                    self._analysis_steps_table,
                    (AnalysisStepsAirtableSchema.job_id["name"], job_id),
                    AnalysisStepsAirtableSchema.screenshot_before_step_execution["name"],
                    event.context,
                    f"job_{job_id}_step_{event.step}.png",
                )
                entries.append({
                    AnalysisStepsAirtableSchema.job_id["name"]: job_id,
                    AnalysisStepsAirtableSchema.index["name"]: index,
                    AnalysisStepsAirtableSchema.step["name"]: event.step,
                    AnalysisStepsAirtableSchema.screenshot_before_step_execution["name"]: [attachment],
                    AnalysisStepsAirtableSchema.step_execution_outcome["name"]: outcome,
                })
                index += 1

        self._logger.info("prepare-analysis-steps", job_id=job_id, status="completed", count=len(entries))
        return entries

    def _get_analysis_steps(self, job_id: str) -> list[RecordDict]:
        """Get existing analysis step record IDs for this job in creation order."""

        self._logger.info("get-analysis-steps", job_id=job_id, status="pending")
        try:
            records = self._analysis_steps_table.all(
                formula=f"{{{AnalysisStepsAirtableSchema.job_id["name"]}}} = '{job_id}'",
                sort=[AnalysisStepsAirtableSchema.index["name"]],  # Sort by index for proper order
            )
            self._logger.info("get-analysis-steps", job_id=job_id, status="completed", count=len(records))
        except Exception as e:
            self._logger.info("get-analysis-steps", job_id=job_id, status="failed", reason=e)
            return []
        else:
            return records

    def _create_analysis_steps(self, entries: list[dict[str, Any]]) -> list[RecordDict]:
        """Create analysis steps records in Airtable."""

        self._logger.info("create-analysis-step", status="pending", count=len(entries))

        if not entries:
            self._logger.info("create-analysis-step", status="failed", reason="No steps data")
            return []

        all_records = []
        batch_size = 100

        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            try:
                records = self._analysis_steps_table.batch_create(batch)
                all_records.extend(records)
                self._logger.info(
                    "create-analysis-step", size=i // batch_size + 1, status="completed", records=len(records)
                )
            except Exception as e:
                self._logger.info("create-analysis-step", size=i // batch_size + 1, status="failed", reason=e)
                for individual_record in batch:
                    try:
                        record = self._analysis_steps_table.create(individual_record)
                        all_records.append(record)
                        self._logger.info("create-analysis-step", size=1, status="completed", record_id=record["id"])
                    except Exception as e:
                        self._logger.info("create-analysis-step", size=1, status="failed", reason=e)

        self._logger.info("create-analysis-step", status="completed", total_records_created=len(all_records))
        return all_records

    async def _prepare_metric(
        self,
        job_response: dict[str, Any],
        expected_source: str,
        expected_pagination_keys: list[str],
        expected_entity_count: int,
        analysis_step_ids: list[str],
    ) -> dict[str, Any]:
        """Prepare metrics entry for Airtable."""

        job_id = job_response["job_id"]
        self._logger.info("prepare-metric", job_id=job_id, status="pending")
        metric = {
            EvaluationMetricsAirtableSchema.run_id["name"]: str(uuid4()),
            EvaluationMetricsAirtableSchema.initiated_at["name"]: datetime.now().isoformat(),
            EvaluationMetricsAirtableSchema.target_site["name"]: job_response.get("url", ""),
            EvaluationMetricsAirtableSchema.label["name"]: job_response.get("label", ""),
            EvaluationMetricsAirtableSchema.source_expected["name"]: expected_source,
            EvaluationMetricsAirtableSchema.pagination_keys_expected["name"]: json.dumps(expected_pagination_keys),
            EvaluationMetricsAirtableSchema.entity_count_expected["name"]: expected_entity_count,
        }

        source = job_response.get("source")
        if not source:
            metric.update({
                EvaluationMetricsAirtableSchema.source_actual["name"]: "",
                EvaluationMetricsAirtableSchema.source_matching["name"]: "no",
                EvaluationMetricsAirtableSchema.pagination_keys_actual["name"]: "[]",
                EvaluationMetricsAirtableSchema.pagination_keys_matching["name"]: "no",
                EvaluationMetricsAirtableSchema.entity_count_actual["name"]: 0,
                EvaluationMetricsAirtableSchema.entity_count_difference["name"]: 100.00,
            })

        else:
            source_actual = source["request"]["url"]

            pagination_strategy = source.get("pagination_strategy") or {}
            pagination_keys_actual = [v["key"] for v in pagination_strategy.values() if v]

            try:
                entities = await self._client.fetch_data(job_id, limit=expected_entity_count, offset=0)
                entity_count_actual = len(entities)
            except Exception:
                entity_count_actual = 0

            source_matching = "no"
            if expected_source and source_actual:
                source_matching = "yes" if expected_source.strip() == source_actual.strip() else "no"

            self._logger.info(
                "prepare-metric",
                job_id=job_id,
                action="compare-urls",
                expected=expected_source,
                actual=source_actual,
                match=source_matching,
            )

            pagination_keys_matching = "no"
            if expected_pagination_keys and pagination_keys_actual:
                expected_set = set(expected_pagination_keys)
                actual_set = set(pagination_keys_actual)
                pagination_keys_matching = "yes" if expected_set == actual_set else "no"

            self._logger.info(
                "prepare-metric",
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
                "prepare-metric",
                job_id=job_id,
                action="calculate-entity-difference",
                expected=expected_entity_count,
                actual=entity_count_actual,
                difference_percent=entity_count_difference,
            )

            metric.update({
                EvaluationMetricsAirtableSchema.source_actual["name"]: source_actual,
                EvaluationMetricsAirtableSchema.source_matching["name"]: source_matching,
                EvaluationMetricsAirtableSchema.pagination_keys_actual["name"]: json.dumps(pagination_keys_actual),
                EvaluationMetricsAirtableSchema.pagination_keys_matching["name"]: pagination_keys_matching,
                EvaluationMetricsAirtableSchema.entity_count_actual["name"]: entity_count_actual,
                EvaluationMetricsAirtableSchema.entity_count_difference["name"]: entity_count_difference,
            })

        metric[EvaluationMetricsAirtableSchema.analysis_steps["name"]] = analysis_step_ids
        metric[EvaluationMetricsAirtableSchema.completed_at["name"]] = datetime.now().isoformat()

        self._logger.info("prepare-metric", job_id=job_id, status="completed")
        return metric

    def _create_metric(self, entry: dict[str, Any]) -> RecordDict:
        """Create metrics record in Airtable."""

        log_kwargs = {
            "run_id": entry[EvaluationMetricsAirtableSchema.run_id["name"]],
            "target_site": entry[EvaluationMetricsAirtableSchema.target_site["name"]],
            "label": entry[EvaluationMetricsAirtableSchema.label["name"]],
        }
        self._logger.info("create-metric", **log_kwargs, status="pending")

        record = self._metrics_table.create(entry)
        self._logger.info("create-metric", **log_kwargs, status="completed", record_id=record["id"])
        return record

    async def evaluate(self, input: ExistingJobInput | NewJobInput) -> None:
        """Evaluate the analysis job."""

        if not self._metrics_table or not self._analysis_steps_table:
            try:
                await self._ensure_tables_exist()
            except Exception:
                await self._ensure_tables_exist()  # retry a second time
            self._metrics_table = self._api.table(env_settings.AIRTABLE_BASE_ID, env_settings.AIRTABLE_METRICS_TABLE)
            self._analysis_steps_table = self._api.table(
                env_settings.AIRTABLE_BASE_ID, env_settings.AIRTABLE_ANALYSIS_STEPS_TABLE
            )

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
            analysis_step_records = self._get_analysis_steps(job_id)
            if not analysis_step_records:
                analysis_steps = self._prepare_analysis_steps(job_id)
                analysis_step_records = self._create_analysis_steps(analysis_steps)

            metric = await self._prepare_metric(
                job_response,
                input.expected_source,
                input.expected_pagination_keys,
                input.expected_entity_count,
                [record["id"] for record in analysis_step_records],
            )

            metric_record = self._create_metric(metric)
            metric_run_id = metric_record["fields"][EvaluationMetricsAirtableSchema.run_id["name"]]
        except Exception as e:
            self._logger.info("evaluate", job_id=job_id, status="failed", reason=e)
            raise

        self._logger.info(
            "evaluate",
            job_id=job_id,
            status="completed",
            metric_run_id=metric_run_id,
            airtable_url=f"https://airtable.com/{env_settings.AIRTABLE_BASE_ID}",
        )
