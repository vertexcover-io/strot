import json
from dataclasses import dataclass
from typing import Any


@dataclass
class LogEvent:
    """Represents a single log event."""

    event: str | None = None
    action: str | None = None
    status: str | None = None
    timestamp: str | None = None
    url: str | None = None
    query: str | None = None
    step_count: int | None = None
    step: str | None = None
    target: str | None = None
    point: Any | None = None
    context: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    result: str | None = None
    reason: str | None = None
    method: str | None = None
    queries: dict[str, Any] | None = None
    data: Any | None = None
    code: str | None = None
    strategy: str | dict[str, Any] | None = None
    potential_pagination_parameters: dict[str, Any] | None = None
    # New unified parameter detection fields (inputs/outputs)
    request: dict[str, Any] | None = None
    pagination_keys: dict[str, Any] | None = None
    dynamic_parameter_keys: list[str] | None = None
    apply_parameters_code: str | None = None
    # New structured extraction fields (inputs/outputs)
    response_length: int | None = None
    preprocessor: dict[str, Any] | None = None
    default_entity_count: int | None = None


@dataclass
class AnalysisStep:
    """Represents an analysis step with sub-events."""

    step_count: int
    status: str | None = None
    method: str | None = None
    url: str | None = None
    queries: dict[str, Any] | None = None
    data: Any | None = None
    reason: str | None = None
    sub_events: list[LogEvent] = None

    def __post_init__(self):
        if self.sub_events is None:
            self.sub_events = []


@dataclass
class ReportData:
    """Complete parsed report data."""

    url: str
    query: str
    analysis_steps: list[AnalysisStep]
    analysis_begin: LogEvent | None = None
    analysis_end: LogEvent | None = None


def parse_jsonl_logs(jsonl_content: str) -> ReportData:  # noqa: C901
    """Parse JSONL log content and extract structured data."""
    lines = [line.strip() for line in jsonl_content.strip().split("\n") if line.strip()]

    events: list[LogEvent] = []

    # Parse JSONL content
    for line in lines:
        try:
            outer_event = json.loads(line)

            # Extract the actual log data from the "message" field if it exists
            if "message" in outer_event:
                try:
                    inner_event = json.loads(outer_event["message"])
                    # Add outer timestamp if inner doesn't have it
                    if "timestamp" not in inner_event and "timestamp" in outer_event:
                        inner_event["timestamp"] = outer_event["timestamp"]
                    events.append(LogEvent(**{k: v for k, v in inner_event.items() if hasattr(LogEvent, k)}))
                except (json.JSONDecodeError, TypeError):
                    # Skip invalid message content
                    continue
            else:
                events.append(LogEvent(**{k: v for k, v in outer_event.items() if hasattr(LogEvent, k)}))
        except (json.JSONDecodeError, TypeError):
            # Skip invalid JSON lines
            continue

    # Initialize report data
    url = ""
    query = ""
    analysis_begin = None
    analysis_end = None
    analysis_steps: list[AnalysisStep] = []

    current_step = None

    # Process events in order
    for event in events:
        event_type = event.event or "unknown"
        action = event.action or ""

        # Main analysis events (support old analysis & request-detection)
        if event_type in ("analysis", "request-detection"):
            if action == "begin":
                analysis_begin = event
                url = event.url or ""
                query = event.query or ""
            elif action == "end":
                analysis_end = event
            elif action == "run-step":
                step_count = event.step_count or 0
                status = event.status or ""

                if status == "pending":
                    # Start a new step
                    current_step = AnalysisStep(step_count=step_count, status="pending", sub_events=[])
                    analysis_steps.append(current_step)
                elif status in ("success", "failed"):
                    # Update the current step with final status
                    if current_step and current_step.step_count == step_count:
                        current_step.status = status
                        current_step.method = event.method
                        current_step.url = event.url
                        current_step.queries = event.queries
                        current_step.data = event.data
                        current_step.reason = event.reason
                    current_step = None  # Close the current step

        # Sub-events go to current step
        elif event_type == "run-step" and current_step:
            current_step.sub_events.append(event)

    # Sort analysis steps by step count
    analysis_steps.sort(key=lambda x: x.step_count)

    return ReportData(
        url=url, query=query, analysis_begin=analysis_begin, analysis_end=analysis_end, analysis_steps=analysis_steps
    )
