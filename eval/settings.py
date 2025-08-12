from pydantic_settings import BaseSettings

from eval.types import AirtableField


class EnvSettings(BaseSettings):
    model_config = {"env_prefix": "STROT_"}

    # API Configuration
    API_BASE_URL: str = "http://localhost:1337"
    """Base URL for the strot API"""

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: str = "strot-user"
    AWS_SECRET_ACCESS_KEY: str = "secretpassword"
    AWS_REGION: str = "us-east-1"
    AWS_S3_ENDPOINT_URL: str = "http://localhost:9000"
    AWS_S3_LOG_BUCKET: str = "job-logs"

    # Airtable Configuration
    AIRTABLE_TOKEN: str
    """Airtable Personal Access Token"""

    AIRTABLE_BASE_ID: str
    """Airtable base ID (starts with 'app...')"""

    AIRTABLE_METRICS_TABLE: str = "metrics"
    """Name of the evaluation metrics table in Airtable"""

    AIRTABLE_ANALYSIS_STEPS_TABLE: str = "analysis_steps"
    """Name of the analysis steps table in Airtable"""


_date_time_options = {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "utc"}

_yes_no_single_select_options = {
    "choices": [{"name": "yes", "color": "greenBright"}, {"name": "no", "color": "redBright"}]
}


class AnalysisStepsAirtableSchema:
    """Analysis steps table schema in Airtable."""

    job_id = AirtableField(name="Job ID", description="Unique Job Identifier", type="singleLineText")
    index = AirtableField(
        name="Step Index",
        description="Sequential order of analysis step execution",
        type="number",
        options={"precision": 0},
    )
    step = AirtableField(
        name="Step Name",
        description="Type of browser action performed during analysis",
        type="singleSelect",
        options={
            "choices": [
                {"name": "fallback", "color": "grayLight2"},
                {"name": "close-overlay-popup", "color": "orangeLight2"},
                {"name": "skip-to-content", "color": "yellowLight2"},
                {"name": "load-more-content", "color": "blueLight2"},
                {"name": "skip-similar-content", "color": "greenLight2"},
            ]
        },
    )
    screenshot_before_step_execution = AirtableField(
        name="Screenshot Before Step Execution",
        description="Page screenshot captured before executing the analysis step",
        type="multipleAttachments",
    )
    step_execution_outcome = AirtableField(
        name="Step Execution Outcome",
        description="Detailed result and status of the step execution",
        type="multilineText",
    )


class EvaluationMetricsAirtableSchema:
    """Evaluation metrics table schema in Airtable."""

    run_id = AirtableField(name="Run ID", description="Unique identifier for the evaluation run", type="singleLineText")
    initiated_at = AirtableField(
        name="Initiated At",
        description="Timestamp when the evaluation was initiated",
        type="dateTime",
        options=_date_time_options,
    )
    completed_at = AirtableField(
        name="Completed At",
        description="Timestamp when the evaluation was completed",
        type="dateTime",
        options=_date_time_options,
    )

    target_site = AirtableField(name="Target Site", description="Analyzed website URL", type="url")
    label = AirtableField(
        name="Label", description="Label identifying the data type being extracted", type="singleLineText"
    )

    source_expected = AirtableField(
        name="Expected Source", description="Expected source that should be discovered", type="url"
    )
    source_actual = AirtableField(name="Actual Source", description="Actual source that was discovered", type="url")
    source_matching = AirtableField(
        name="Source Matching",
        description="Whether the discovered and expected sources match",
        type="singleSelect",
        options=_yes_no_single_select_options,
    )

    pagination_keys_expected = AirtableField(
        name="Expected Pagination Keys",
        description="Expected pagination parameters that should be detected",
        type="singleLineText",
    )
    pagination_keys_actual = AirtableField(
        name="Actual Pagination Keys",
        description="Actual pagination parameters that were detected",
        type="singleLineText",
    )
    pagination_keys_matching = AirtableField(
        name="Pagination Keys Matching",
        description="Whether the detected and expected pagination keys match",
        type="singleSelect",
        options=_yes_no_single_select_options,
    )

    entity_count_expected = AirtableField(
        name="Expected Entity Count",
        description="Expected number of data entities that should be extracted",
        type="number",
        options={"precision": 0},
    )
    entity_count_actual = AirtableField(
        name="Actual Entity Count",
        description="Actual number of data entities that were extracted",
        type="number",
        options={"precision": 0},
    )
    entity_count_difference = AirtableField(
        name="Entity Count Difference (%)",
        description="Percentage difference between expected and actual entity counts",
        type="number",
        options={"precision": 2},
    )

    analysis_steps = AirtableField(
        name="Analysis Steps",
        description="Link to analysis steps records for this job",
        type="multipleRecordLinks",
        options={"linkedTableId": None},  # Will be updated in runtime
    )

    # This field should be populated manually through UI after the evaluation is completed
    comment = AirtableField(
        name="Comment", description="Optional notes or observations about this evaluation", type="multilineText"
    )


env_settings = EnvSettings()
