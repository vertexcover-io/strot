from typing import Any, ClassVar, NotRequired, TypedDict


class AirtableField(TypedDict):
    name: str
    description: str
    type: str
    options: NotRequired[dict[str, Any]]


class Attachment(TypedDict):
    url: str


_date_time_options = {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "utc"}

_yes_no_single_select_options = {
    "choices": [{"name": "yes", "color": "greenBright"}, {"name": "no", "color": "redBright"}]
}


class AnalysisStepsAirtableSchema:
    """Analysis steps table schema in Airtable."""

    job_id: ClassVar[AirtableField] = {
        "name": "Job ID",
        "description": "Unique Job Identifier",
        "type": "singleLineText",
    }
    index: ClassVar[AirtableField] = {
        "name": "Step Index",
        "description": "Sequential order of analysis step execution",
        "type": "number",
        "options": {"precision": 0},
    }
    step: ClassVar[AirtableField] = {
        "name": "Step Name",
        "description": "Type of browser action performed during analysis",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "fallback", "color": "grayLight2"},
                {"name": "close-overlay-popup", "color": "orangeLight2"},
                {"name": "skip-to-content", "color": "yellowLight2"},
                {"name": "load-more-content", "color": "blueLight2"},
                {"name": "skip-similar-content", "color": "greenLight2"},
            ]
        },
    }
    screenshot_before_step_execution: ClassVar[AirtableField] = {
        "name": "Screenshot Before Step Execution",
        "description": "Page screenshot captured before executing the analysis step",
        "type": "multipleAttachments",
    }
    step_execution_outcome: ClassVar[AirtableField] = {
        "name": "Step Execution Outcome",
        "description": "Detailed result and status of the step execution",
        "type": "multilineText",
    }

    @classmethod
    def fields(cls) -> list[AirtableField]:
        return [
            cls.job_id,
            cls.index,
            cls.step,
            cls.screenshot_before_step_execution,
            cls.step_execution_outcome,
        ]


class RequestDetectionAirtableSchema:
    """Request detection evaluation table schema in Airtable."""

    run_id: ClassVar[AirtableField] = {
        "name": "Run ID",
        "description": "Unique identifier for the evaluation run",
        "type": "singleLineText",
    }
    initiated_at: ClassVar[AirtableField] = {
        "name": "Initiated At",
        "description": "Timestamp when the evaluation was initiated",
        "type": "dateTime",
        "options": _date_time_options,
    }
    completed_at: ClassVar[AirtableField] = {
        "name": "Completed At",
        "description": "Timestamp when the evaluation was completed",
        "type": "dateTime",
        "options": _date_time_options,
    }

    site_url: ClassVar[AirtableField] = {"name": "Site URL", "description": "Website URL being analyzed", "type": "url"}
    query: ClassVar[AirtableField] = {"name": "Query", "description": "Analysis query used", "type": "singleLineText"}

    expected_source: ClassVar[AirtableField] = {
        "name": "Expected Source",
        "description": "Expected source URL",
        "type": "url",
    }
    actual_source: ClassVar[AirtableField] = {
        "name": "Actual Source",
        "description": "Detected source URL",
        "type": "url",
    }
    source_matching: ClassVar[AirtableField] = {
        "name": "Source Matching",
        "description": "Whether detected and expected sources match",
        "type": "singleSelect",
        "options": _yes_no_single_select_options,
    }

    comment: ClassVar[AirtableField] = {
        "name": "Comment",
        "description": "Optional evaluation notes",
        "type": "multilineText",
    }

    @classmethod
    def fields(cls) -> list[AirtableField]:
        return [
            cls.run_id,
            cls.initiated_at,
            cls.completed_at,
            cls.site_url,
            cls.query,
            cls.expected_source,
            cls.actual_source,
            cls.source_matching,
            cls.comment,
        ]


class PaginationDetectionAirtableSchema:
    """Pagination detection evaluation table schema in Airtable."""

    run_id: ClassVar[AirtableField] = {
        "name": "Run ID",
        "description": "Unique identifier for the evaluation run",
        "type": "singleLineText",
    }
    initiated_at: ClassVar[AirtableField] = {
        "name": "Initiated At",
        "description": "Timestamp when the evaluation was initiated",
        "type": "dateTime",
        "options": _date_time_options,
    }
    completed_at: ClassVar[AirtableField] = {
        "name": "Completed At",
        "description": "Timestamp when the evaluation was completed",
        "type": "dateTime",
        "options": _date_time_options,
    }

    request: ClassVar[AirtableField] = {
        "name": "Request",
        "description": "Request object being analyzed",
        "type": "multilineText",
    }

    expected_pagination_keys: ClassVar[AirtableField] = {
        "name": "Expected Pagination Keys",
        "description": "Expected pagination parameter names",
        "type": "singleLineText",
    }
    actual_pagination_keys: ClassVar[AirtableField] = {
        "name": "Actual Pagination Keys",
        "description": "Detected pagination parameter names",
        "type": "singleLineText",
    }
    pagination_keys_matching: ClassVar[AirtableField] = {
        "name": "Pagination Keys Matching",
        "description": "Whether detected and expected pagination keys match",
        "type": "singleSelect",
        "options": _yes_no_single_select_options,
    }

    comment: ClassVar[AirtableField] = {
        "name": "Comment",
        "description": "Optional evaluation notes",
        "type": "multilineText",
    }

    @classmethod
    def fields(cls) -> list[AirtableField]:
        return [
            cls.run_id,
            cls.initiated_at,
            cls.completed_at,
            cls.request,
            cls.expected_pagination_keys,
            cls.actual_pagination_keys,
            cls.pagination_keys_matching,
            cls.comment,
        ]


class CodeGenerationAirtableSchema:
    """Code generation evaluation table schema in Airtable."""

    run_id: ClassVar[AirtableField] = {
        "name": "Run ID",
        "description": "Unique identifier for the evaluation run",
        "type": "singleLineText",
    }
    initiated_at: ClassVar[AirtableField] = {
        "name": "Initiated At",
        "description": "Timestamp when the evaluation was initiated",
        "type": "dateTime",
        "options": _date_time_options,
    }
    completed_at: ClassVar[AirtableField] = {
        "name": "Completed At",
        "description": "Timestamp when the evaluation was completed",
        "type": "dateTime",
        "options": _date_time_options,
    }

    response: ClassVar[AirtableField] = {
        "name": "Response",
        "description": "Response object being analyzed",
        "type": "multilineText",
    }  # set the value to "",  before writing to airtable

    expected_entity_count: ClassVar[AirtableField] = {
        "name": "Expected Entity Count",
        "description": "Expected number of extracted entities",
        "type": "number",
        "options": {"precision": 0},
    }
    actual_entity_count: ClassVar[AirtableField] = {
        "name": "Actual Entity Count",
        "description": "Actual number of extracted entities",
        "type": "number",
        "options": {"precision": 0},
    }
    entity_count_difference: ClassVar[AirtableField] = {
        "name": "Entity Count Difference (%)",
        "description": "Percentage difference between expected and actual counts",
        "type": "number",
        "options": {"precision": 2},
    }

    generation_successful: ClassVar[AirtableField] = {
        "name": "Generation Successful",
        "description": "Whether code generation succeeded",
        "type": "singleSelect",
        "options": _yes_no_single_select_options,
    }

    comment: ClassVar[AirtableField] = {
        "name": "Comment",
        "description": "Optional evaluation notes",
        "type": "multilineText",
    }

    @classmethod
    def fields(cls) -> list[AirtableField]:
        return [
            cls.run_id,
            cls.initiated_at,
            cls.completed_at,
            cls.response,
            cls.expected_entity_count,
            cls.actual_entity_count,
            cls.entity_count_difference,
            cls.generation_successful,
            cls.comment,
        ]


class EvaluationMetricsAirtableSchema:
    """Evaluation metrics table schema in Airtable."""

    run_id: ClassVar[AirtableField] = {
        "name": "Run ID",
        "description": "Unique identifier for the evaluation run",
        "type": "singleLineText",
    }
    initiated_at: ClassVar[AirtableField] = {
        "name": "Initiated At",
        "description": "Timestamp when the evaluation was initiated",
        "type": "dateTime",
        "options": _date_time_options,
    }
    completed_at: ClassVar[AirtableField] = {
        "name": "Completed At",
        "description": "Timestamp when the evaluation was completed",
        "type": "dateTime",
        "options": _date_time_options,
    }

    target_site: ClassVar[AirtableField] = {"name": "Target Site", "description": "Analyzed website URL", "type": "url"}
    label: ClassVar[AirtableField] = {
        "name": "Label",
        "description": "Label identifying the data type being extracted",
        "type": "singleLineText",
    }

    source_expected: ClassVar[AirtableField] = {
        "name": "Expected Source",
        "description": "Expected source that should be discovered",
        "type": "url",
    }
    source_actual: ClassVar[AirtableField] = {
        "name": "Actual Source",
        "description": "Actual source that was discovered",
        "type": "url",
    }
    source_matching: ClassVar[AirtableField] = {
        "name": "Source Matching",
        "description": "Whether the discovered and expected sources match",
        "type": "singleSelect",
        "options": _yes_no_single_select_options,
    }

    pagination_keys_expected: ClassVar[AirtableField] = {
        "name": "Expected Pagination Keys",
        "description": "Expected pagination parameters that should be detected",
        "type": "singleLineText",
    }
    pagination_keys_actual: ClassVar[AirtableField] = {
        "name": "Actual Pagination Keys",
        "description": "Actual pagination parameters that were detected",
        "type": "singleLineText",
    }
    pagination_keys_matching: ClassVar[AirtableField] = {
        "name": "Pagination Keys Matching",
        "description": "Whether the detected and expected pagination keys match",
        "type": "singleSelect",
        "options": _yes_no_single_select_options,
    }

    entity_count_expected: ClassVar[AirtableField] = {
        "name": "Expected Entity Count",
        "description": "Expected number of data entities that should be extracted",
        "type": "number",
        "options": {"precision": 0},
    }
    entity_count_actual: ClassVar[AirtableField] = {
        "name": "Actual Entity Count",
        "description": "Actual number of data entities that were extracted",
        "type": "number",
        "options": {"precision": 0},
    }
    entity_count_difference: ClassVar[AirtableField] = {
        "name": "Entity Count Difference (%)",
        "description": "Percentage difference between expected and actual entity counts",
        "type": "number",
        "options": {"precision": 2},
    }

    analysis_steps: ClassVar[AirtableField] = {
        "name": "Analysis Steps",
        "description": "Link to analysis steps records for this job",
        "type": "multipleRecordLinks",
        "options": {"linkedTableId": None},  # Will be updated in runtime
    }

    # This field should be populated manually through UI after the evaluation is completed
    comment: ClassVar[AirtableField] = {
        "name": "Comment",
        "description": "Optional notes or observations about this evaluation",
        "type": "multilineText",
    }

    @classmethod
    def fields(cls, analysis_steps_table_id: str) -> list[AirtableField]:
        return [
            cls.run_id,
            cls.initiated_at,
            cls.completed_at,
            cls.target_site,
            cls.label,
            cls.source_expected,
            cls.source_actual,
            cls.source_matching,
            cls.pagination_keys_expected,
            cls.pagination_keys_actual,
            cls.pagination_keys_matching,
            cls.entity_count_expected,
            cls.entity_count_actual,
            cls.entity_count_difference,
            cls.analysis_steps | {"options": {"linkedTableId": analysis_steps_table_id}},
            cls.comment,
        ]
