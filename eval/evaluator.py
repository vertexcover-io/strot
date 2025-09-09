from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from json_schema_to_pydantic import create_model
from pyairtable.api.types import RecordDict
from pydantic import BaseModel

from strot.analyzer import Analyzer
from strot.browser import launch_browser
from strot.browser.tab import Tab
from strot.logging import LoggerType, get_logger
from strot.schema.request import Request
from strot.schema.request.detail import RequestDetail
from strot.schema.response import Response
from strot.schema.source import OldSource, Source
from strot.type_adapter import TypeAdapter

from . import inputs
from .airtable import schema
from .airtable.client import AirtableClient
from .client import StrotClient
from .log_parser import parse_jsonl_logs
from .settings import env_settings


class JobEvaluator:
    def __init__(self, airtable_client: AirtableClient, logger: LoggerType | None = None):
        self._logger = logger or get_logger()
        self._client = StrotClient(logger=self._logger)
        self._airtable_client = airtable_client

    async def _prepare_analysis_steps(self, job_id: str) -> list[dict[str, Any]]:
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

                analysis_steps_table = await self._airtable_client.get_analysis_steps_table()
                attachment = self._airtable_client.upload_attachment(
                    table=analysis_steps_table,
                    primary_field_kv=(schema.AnalysisStepsAirtableSchema.job_id["name"], job_id),
                    attachment_field=schema.AnalysisStepsAirtableSchema.screenshot_before_step_execution["name"],
                    attachment_data=base64.b64decode(event.context),
                    attachment_name=f"job_{job_id}_step_{event.step}.png",
                )
                entries.append({
                    schema.AnalysisStepsAirtableSchema.job_id["name"]: job_id,
                    schema.AnalysisStepsAirtableSchema.index["name"]: index,
                    schema.AnalysisStepsAirtableSchema.step["name"]: event.step,
                    schema.AnalysisStepsAirtableSchema.screenshot_before_step_execution["name"]: [attachment],
                    schema.AnalysisStepsAirtableSchema.step_execution_outcome["name"]: outcome,
                })
                index += 1

        self._logger.info("prepare-analysis-steps", job_id=job_id, status="completed", count=len(entries))
        return entries

    async def _get_analysis_steps(self, job_id: str) -> list[RecordDict]:
        """Get existing analysis step record IDs for this job in creation order."""

        self._logger.info("get-analysis-steps", job_id=job_id, status="pending")
        try:
            analysis_steps_table = await self._airtable_client.get_analysis_steps_table()
            records = analysis_steps_table.all(
                formula=f"{{{schema.AnalysisStepsAirtableSchema.job_id["name"]}}} = '{job_id}'",
                sort=[schema.AnalysisStepsAirtableSchema.index["name"]],  # Sort by index for proper order
            )
            self._logger.info("get-analysis-steps", job_id=job_id, status="completed", count=len(records))
        except Exception as e:
            self._logger.info("get-analysis-steps", job_id=job_id, status="failed", reason=e)
            return []
        else:
            return records

    async def _create_analysis_steps(self, entries: list[dict[str, Any]]) -> list[RecordDict]:
        """Create analysis steps records in Airtable."""

        self._logger.info("create-analysis-step", status="pending", count=len(entries))

        if not entries:
            self._logger.info("create-analysis-step", status="failed", reason="No steps data")
            return []

        analysis_steps_table = await self._airtable_client.get_analysis_steps_table()
        all_records = []
        batch_size = 100

        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            try:
                records = analysis_steps_table.batch_create(batch)
                all_records.extend(records)
                self._logger.info(
                    "create-analysis-step", size=i // batch_size + 1, status="completed", records=len(records)
                )
            except Exception as e:
                self._logger.info("create-analysis-step", size=i // batch_size + 1, status="failed", reason=e)
                for individual_record in batch:
                    try:
                        record = analysis_steps_table.create(individual_record)
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
        expected_dynamic_keys: list[str],
        expected_entity_count: int,
        analysis_step_ids: list[str],
    ) -> dict[str, Any]:
        """Prepare metrics entry for Airtable."""

        job_id = job_response["job_id"]
        self._logger.info("prepare-metric", job_id=job_id, status="pending")
        metric = {
            schema.EvaluationMetricsAirtableSchema.run_id["name"]: str(uuid4()),
            schema.EvaluationMetricsAirtableSchema.initiated_at["name"]: datetime.now().isoformat(),
            schema.EvaluationMetricsAirtableSchema.target_site["name"]: job_response.get("url", ""),
            schema.EvaluationMetricsAirtableSchema.label["name"]: job_response.get("label", ""),
            schema.EvaluationMetricsAirtableSchema.source_expected["name"]: expected_source,
            schema.EvaluationMetricsAirtableSchema.pagination_keys_expected["name"]: json.dumps(
                expected_pagination_keys
            ),
            schema.EvaluationMetricsAirtableSchema.dynamic_keys_expected["name"]: json.dumps(expected_dynamic_keys),
            schema.EvaluationMetricsAirtableSchema.entity_count_expected["name"]: expected_entity_count,
        }

        source = job_response.get("source")
        if not source:
            metric.update({
                schema.EvaluationMetricsAirtableSchema.source_actual["name"]: "",
                schema.EvaluationMetricsAirtableSchema.source_matching["name"]: "no",
                schema.EvaluationMetricsAirtableSchema.pagination_keys_actual["name"]: "[]",
                schema.EvaluationMetricsAirtableSchema.pagination_keys_matching["name"]: "no",
                schema.EvaluationMetricsAirtableSchema.dynamic_keys_actual["name"]: "[]",
                schema.EvaluationMetricsAirtableSchema.dynamic_keys_matching["name"]: "no",
                schema.EvaluationMetricsAirtableSchema.entity_count_actual["name"]: 0,
                schema.EvaluationMetricsAirtableSchema.entity_count_difference["name"]: 100.00,
            })

        else:
            source_instance = TypeAdapter(Source | OldSource).validate_python(source)
            if isinstance(source_instance, OldSource):
                source_instance = source_instance.as_new_source()

            source_actual = source_instance.request_detail.request.url

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

            pagination_keys_actual = []
            if source_instance.request_detail.pagination_info:
                pagination_keys_actual = source_instance.request_detail.pagination_info.keys

            dynamic_keys_actual = list(source_instance.request_detail.dynamic_parameters)

            pagination_keys_matching = "no"
            if expected_pagination_keys and pagination_keys_actual:
                expected_set = set(expected_pagination_keys)
                actual_set = set(pagination_keys_actual)
                pagination_keys_matching = "yes" if expected_set == actual_set else "no"

            dynamic_keys_matching = "no"
            if expected_dynamic_keys and dynamic_keys_actual:
                expected_set = set(expected_dynamic_keys)
                actual_set = set(dynamic_keys_actual)
                dynamic_keys_matching = "yes" if expected_set == actual_set else "no"

            self._logger.info(
                "prepare-metric",
                job_id=job_id,
                action="compare-parameter-keys",
                expected_pagination_keys=expected_pagination_keys,
                actual_pagination_keys=pagination_keys_actual,
                pagination_keys_matching=pagination_keys_matching,
                expected_dynamic_keys=expected_dynamic_keys,
                actual_dynamic_keys=dynamic_keys_actual,
                dynamic_keys_matching=dynamic_keys_matching,
            )

            try:
                entities = await self._client.fetch_data(job_id, limit=expected_entity_count, offset=0)
                entity_count_actual = len(entities)
            except Exception:
                entity_count_actual = 0

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
                schema.EvaluationMetricsAirtableSchema.source_actual["name"]: source_actual,
                schema.EvaluationMetricsAirtableSchema.source_matching["name"]: source_matching,
                schema.EvaluationMetricsAirtableSchema.pagination_keys_actual["name"]: json.dumps(
                    pagination_keys_actual
                ),
                schema.EvaluationMetricsAirtableSchema.pagination_keys_matching["name"]: pagination_keys_matching,
                schema.EvaluationMetricsAirtableSchema.dynamic_keys_actual["name"]: json.dumps(dynamic_keys_actual),
                schema.EvaluationMetricsAirtableSchema.dynamic_keys_matching["name"]: dynamic_keys_matching,
                schema.EvaluationMetricsAirtableSchema.entity_count_actual["name"]: entity_count_actual,
                schema.EvaluationMetricsAirtableSchema.entity_count_difference["name"]: entity_count_difference,
            })

        metric[schema.EvaluationMetricsAirtableSchema.analysis_steps["name"]] = analysis_step_ids
        metric[schema.EvaluationMetricsAirtableSchema.completed_at["name"]] = datetime.now().isoformat()

        self._logger.info("prepare-metric", job_id=job_id, status="completed")
        return metric

    async def _create_metric(self, entry: dict[str, Any]) -> RecordDict:
        """Create metrics record in Airtable."""

        log_kwargs = {
            "run_id": entry[schema.EvaluationMetricsAirtableSchema.run_id["name"]],
            "target_site": entry[schema.EvaluationMetricsAirtableSchema.target_site["name"]],
            "label": entry[schema.EvaluationMetricsAirtableSchema.label["name"]],
        }
        self._logger.info("create-metric", **log_kwargs, status="pending")

        metrics_table = await self._airtable_client.get_metrics_table()
        record = metrics_table.create(entry)
        self._logger.info("create-metric", **log_kwargs, status="completed", record_id=record["id"])
        return record

    async def evaluate(self, input: inputs.JobBasedInput) -> None:
        """Evaluate the analysis job."""

        if isinstance(input, inputs.NewJobInput):
            job_id = await self._client.create_job(input.site_url, input.label)
        elif isinstance(input, inputs.ExistingJobInput):
            job_id = input.job_id
        else:
            raise ValueError(f"Unsupported input type: {type(input)}")  # noqa: TRY004

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
            analysis_step_records = await self._get_analysis_steps(job_id)
            if not analysis_step_records:
                analysis_steps = await self._prepare_analysis_steps(job_id)
                analysis_step_records = await self._create_analysis_steps(analysis_steps)

            metric = await self._prepare_metric(
                job_response,
                input.expected_source,
                input.expected_pagination_keys,
                input.expected_dynamic_keys,
                input.expected_entity_count,
                [record["id"] for record in analysis_step_records],
            )

            metric_record = await self._create_metric(metric)
            metric_run_id = metric_record["fields"][schema.EvaluationMetricsAirtableSchema.run_id["name"]]
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


class TaskEvaluator:
    def __init__(self, airtable_client: AirtableClient, logger: LoggerType | None = None):
        self._logger = logger or get_logger()
        self._analyzer = Analyzer(logger=self._logger)
        self._airtable_client = airtable_client

    async def evaluate_request_detection(self, input: inputs.RequestDetectionInput) -> None:
        """Evaluate request detection for given input."""

        request_detection_table = await self._airtable_client.get_request_detection_table()

        run_id = str(uuid4())
        self._logger.info("evaluate-request-detection", run_id=run_id, status="pending")

        record = {
            schema.RequestDetectionAirtableSchema.run_id["name"]: run_id,
            schema.RequestDetectionAirtableSchema.initiated_at["name"]: datetime.now().isoformat(),
            schema.RequestDetectionAirtableSchema.site_url["name"]: input.site_url,
            schema.RequestDetectionAirtableSchema.query["name"]: input.query,
            schema.RequestDetectionAirtableSchema.expected_source["name"]: input.expected_source,
            schema.RequestDetectionAirtableSchema.comment["name"]: "",
        }

        try:
            actual_source = await get_source_url(self._analyzer, url=input.site_url, query=input.query)
        except Exception as e:
            actual_source = None
            record[schema.RequestDetectionAirtableSchema.comment["name"]] = str(e)

        source_matching = "no"
        if input.expected_source and actual_source is not None:
            source_matching = "yes" if input.expected_source.strip() == actual_source.strip() else "no"

        record[schema.RequestDetectionAirtableSchema.actual_source["name"]] = actual_source or ""
        record[schema.RequestDetectionAirtableSchema.source_matching["name"]] = source_matching
        record[schema.RequestDetectionAirtableSchema.completed_at["name"]] = datetime.now().isoformat()

        request_detection_table.create(record)
        self._logger.info("evaluate-request-detection", run_id=run_id, status="completed", match=source_matching)

    async def evaluate_parameter_detection(self, input: inputs.ParameterDetectionInput) -> None:
        """Evaluate parameter detection for given input."""

        parameter_detection_table = await self._airtable_client.get_parameter_detection_table()

        run_id = str(uuid4())
        self._logger.info("evaluate-parameter-detection", run_id=run_id, status="pending")

        record = {
            schema.ParameterDetectionAirtableSchema.run_id["name"]: run_id,
            schema.ParameterDetectionAirtableSchema.initiated_at["name"]: datetime.now().isoformat(),
            schema.ParameterDetectionAirtableSchema.request["name"]: input.request.model_dump_json(indent=2),
            schema.ParameterDetectionAirtableSchema.expected_pagination_keys["name"]: json.dumps(
                input.expected_pagination_keys
            ),
            schema.ParameterDetectionAirtableSchema.expected_dynamic_keys["name"]: json.dumps(
                input.expected_dynamic_keys
            ),
            schema.ParameterDetectionAirtableSchema.comment["name"]: "",
        }

        try:
            pagination_keys, dynamic_keys = await get_pagination_and_dynamic_parameter_keys(
                self._analyzer, request=input.request
            )

            # Evaluate pagination keys separately
            pagination_matching = "no"
            if input.expected_pagination_keys and pagination_keys:
                expected_set = set(input.expected_pagination_keys)
                actual_set = set(pagination_keys)
                pagination_matching = "yes" if expected_set == actual_set else "no"
            elif not input.expected_pagination_keys and not pagination_keys:
                pagination_matching = "yes"  # Both empty

            # Evaluate dynamic keys separately
            dynamic_matching = "no"
            if input.expected_dynamic_keys and dynamic_keys:
                expected_set = set(input.expected_dynamic_keys)
                actual_set = set(dynamic_keys)
                dynamic_matching = "yes" if expected_set == actual_set else "no"
            elif not input.expected_dynamic_keys and not dynamic_keys:
                dynamic_matching = "yes"  # Both empty

            record.update({
                schema.ParameterDetectionAirtableSchema.actual_pagination_keys["name"]: json.dumps(pagination_keys),
                schema.ParameterDetectionAirtableSchema.pagination_keys_matching["name"]: pagination_matching,
                schema.ParameterDetectionAirtableSchema.actual_dynamic_keys["name"]: json.dumps(dynamic_keys),
                schema.ParameterDetectionAirtableSchema.dynamic_keys_matching["name"]: dynamic_matching,
            })

        except Exception as e:
            record.update({
                schema.ParameterDetectionAirtableSchema.actual_pagination_keys["name"]: json.dumps([]),
                schema.ParameterDetectionAirtableSchema.pagination_keys_matching["name"]: "no",
                schema.ParameterDetectionAirtableSchema.actual_dynamic_keys["name"]: json.dumps([]),
                schema.ParameterDetectionAirtableSchema.dynamic_keys_matching["name"]: "no",
                schema.ParameterDetectionAirtableSchema.comment["name"]: f"ERROR: {e!s}",
            })

        record[schema.ParameterDetectionAirtableSchema.completed_at["name"]] = datetime.now().isoformat()

        parameter_detection_table.create(record)
        self._logger.info(
            "evaluate-parameter-detection",
            run_id=run_id,
            status="completed",
            pagination_match=record[schema.ParameterDetectionAirtableSchema.pagination_keys_matching["name"]],
            dynamic_match=record[schema.ParameterDetectionAirtableSchema.dynamic_keys_matching["name"]],
        )

    async def evaluate_structured_extraction(self, input: inputs.StructuredExtractionInput) -> None:
        """Evaluate structured extraction for given input."""

        output_schema = create_model(json.loads(input.output_schema_file.read_text()))
        structured_extraction_table = await self._airtable_client.get_structured_extraction_table()

        run_id = str(uuid4())
        self._logger.info("evaluate-structured-extraction", run_id=run_id, status="pending")

        record = {
            schema.StructuredExtractionAirtableSchema.run_id["name"]: run_id,
            schema.StructuredExtractionAirtableSchema.initiated_at["name"]: datetime.now().isoformat(),
            schema.StructuredExtractionAirtableSchema.response["name"]: input.response.model_dump_json(
                indent=2, exclude={"value"}
            ),
            schema.StructuredExtractionAirtableSchema.expected_entity_count["name"]: input.expected_entity_count,
            schema.StructuredExtractionAirtableSchema.comment["name"]: "",
        }

        try:
            actual_entity_count = await get_entity_count(
                self._analyzer, response=input.response, output_schema=output_schema
            )
            generation_successful = "yes"
        except Exception as e:
            actual_entity_count = None
            generation_successful = "no"
            record[schema.StructuredExtractionAirtableSchema.comment["name"]] = str(e)

        entity_count_difference = 0.0
        if input.expected_entity_count and actual_entity_count is not None:
            difference = abs(input.expected_entity_count - actual_entity_count)
            entity_count_difference = (difference / input.expected_entity_count) * 100
            entity_count_difference = round(entity_count_difference, 2)

        record[schema.StructuredExtractionAirtableSchema.actual_entity_count["name"]] = actual_entity_count
        record[schema.StructuredExtractionAirtableSchema.entity_count_difference["name"]] = entity_count_difference
        record[schema.StructuredExtractionAirtableSchema.generation_successful["name"]] = generation_successful

        structured_extraction_table.create(record)
        self._logger.info(
            "evaluate-structured-extraction",
            run_id=run_id,
            status="completed",
            success=generation_successful,
            difference=entity_count_difference,
        )

    async def evaluate(self, input: inputs.TaskBasedInput) -> None:
        """Route input to appropriate evaluation method."""

        if isinstance(input, inputs.RequestDetectionInput):
            await self.evaluate_request_detection(input)
        elif isinstance(input, inputs.StructuredExtractionInput):
            await self.evaluate_structured_extraction(input)
        elif isinstance(input, inputs.ParameterDetectionInput):
            await self.evaluate_parameter_detection(input)
        else:
            raise ValueError(f"Unsupported input type: {type(input)}")  # noqa: TRY004


async def get_source_url(
    analyzer: Analyzer,
    *,
    url: str,
    query: str,
):
    async with launch_browser(str(env_settings.BROWSER_MODE_OR_WS_URL)) as browser:
        browser_ctx = await browser.new_context(bypass_csp=True)
        tab = Tab(browser_ctx)
        try:
            await tab.goto(url)
            response = await analyzer.discover_relevant_response(tab, query, max_steps=20)
            return response.request.url if response else None
        finally:
            with contextlib.suppress(Exception):
                await tab.reset()
                await browser_ctx.close()


async def get_pagination_and_dynamic_parameter_keys(
    analyzer: Analyzer,
    *,
    request: Request,
):
    request_detail = await analyzer.build_request_detail(request)
    pagination_keys = []
    if request_detail.pagination_info:
        pagination_keys = request_detail.pagination_info.keys
    return pagination_keys, list(request_detail.dynamic_parameters)


async def get_entity_count(
    analyzer: Analyzer,
    *,
    response: Response,
    output_schema: type[BaseModel],
):
    if not response.value:
        request_detail = RequestDetail(request=response.request)
        try:
            fetched_response = await request_detail.make_request()
            response.value = await fetched_response.text()
        except Exception as e:
            raise ValueError(f"Failed to fetch response: {e}") from e

    response_detail = await analyzer.build_response_detail(response, output_schema)
    return response_detail.default_entity_count
