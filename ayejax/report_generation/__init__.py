import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

__all__ = ("generate_report",)


def generate_report(jsonl_content: str) -> str:  # noqa: C901
    """
    Generate an HTML report from JSONL log content showing analysis insights.

    Args:
        jsonl_content: JSONL formatted log content as string

    Returns:
        HTML report as string
    """
    # Parse JSONL content
    lines = [line.strip() for line in jsonl_content.strip().split("\n") if line.strip()]
    events = []

    for line in lines:
        try:
            outer_event = json.loads(line)
            # Extract the actual log data from the "message" field if it exists
            if "message" in outer_event:
                try:
                    inner_event = json.loads(outer_event["message"])
                    # Add outer timestamp if inner doesn't have it
                    if "timestamp" not in inner_event:
                        inner_event["timestamp"] = outer_event.get("timestamp", "")
                    events.append(inner_event)
                except (json.JSONDecodeError, TypeError):
                    # If message is not valid JSON, treat as string
                    events.append({
                        "event": "log",
                        "message": outer_event["message"],
                        "timestamp": outer_event.get("timestamp", ""),
                    })
            else:
                events.append(outer_event)
        except json.JSONDecodeError:
            continue

    # Group events by analysis flow
    analysis_steps = []
    current_step = None
    pagination_detections = []
    current_pagination_detection = None  # Track current detection attempt
    code_generations = []
    url = ""
    query = ""
    analysis_begin = None
    analysis_end = None

    # Extract basic info from begin event
    for event in events:
        if event.get("event") == "analysis" and event.get("action") == "begin":
            url = event.get("url", "")
            query = event.get("query", "")
            analysis_begin = event
            break

    for event in events:
        event_type = event.get("event", "unknown")
        action = event.get("action", "")

        # Track analysis begin/end
        if event_type == "analysis":
            if action == "begin":
                analysis_begin = event
            elif action == "end":
                analysis_end = event
            elif action == "run-step":
                step_count = event.get("step_count", 0)
                status = event.get("status", "")

                # Skip pending events entirely
                if status == "pending":
                    continue

                # Find or create the step
                step = None
                for s in analysis_steps:
                    if s["step_count"] == step_count:
                        step = s
                        break

                if not step:
                    step = {
                        "step_count": step_count,
                        "status": status,
                        "method": event.get("method", ""),
                        "url": event.get("url", ""),
                        "queries": event.get("queries", ""),
                        "data": event.get("data", ""),
                        "reason": event.get("reason", ""),
                        "sub_events": [],
                    }
                    analysis_steps.append(step)
                else:
                    # Update with success/failed info
                    step["status"] = status
                    step["method"] = event.get("method", "")
                    step["url"] = event.get("url", "")
                    step["queries"] = event.get("queries", "")
                    step["data"] = event.get("data", "")
                    step["reason"] = event.get("reason", "")

                current_step = step
            elif action == "detect-pagination":
                status = event.get("status", "")
                if status == "pending":
                    # Start a new detection attempt
                    current_pagination_detection = {
                        "status": "pending",
                        "request_parameters": event.get("request_parameters", {}),
                        "strategy": "",
                        "page_number_key": "",
                        "offset_key": "",
                        "limit_key": "",
                        "cursor_key": "",
                        "base_offset": "",
                        "start_cursor": "",
                        "reason": "",
                        "llm_calls": [],
                    }
                else:
                    # Complete the current detection attempt
                    if current_pagination_detection:
                        current_pagination_detection.update({
                            "status": status,
                            "strategy": event.get("strategy", ""),
                            "page_number_key": event.get("page_number_key", ""),
                            "offset_key": event.get("offset_key", ""),
                            "limit_key": event.get("limit_key", ""),
                            "cursor_key": event.get("cursor_key", ""),
                            "base_offset": event.get("base_offset", ""),
                            "start_cursor": event.get("start_cursor", ""),
                            "reason": event.get("reason", ""),
                        })
                        pagination_detections.append(current_pagination_detection)
                        current_pagination_detection = None
                    else:
                        # Fallback: create detection without pending start
                        pagination_detections.append({
                            "status": status,
                            "request_parameters": event.get("request_parameters", {}),
                            "strategy": event.get("strategy", ""),
                            "page_number_key": event.get("page_number_key", ""),
                            "offset_key": event.get("offset_key", ""),
                            "limit_key": event.get("limit_key", ""),
                            "cursor_key": event.get("cursor_key", ""),
                            "base_offset": event.get("base_offset", ""),
                            "start_cursor": event.get("start_cursor", ""),
                            "reason": event.get("reason", ""),
                            "llm_calls": [],
                        })
            elif action == "code-generation":  # noqa: SIM102
                # Skip pending events
                if event.get("status") != "pending":
                    code_generations.append({
                        "status": event.get("status", ""),
                        "code": event.get("code", ""),
                        "reason": event.get("reason", ""),
                    })

        # Track run-step sub-events (skip pending status)
        elif event_type == "run-step":
            # Skip pending events
            if event.get("status") == "pending":
                continue

            # Find the current step by looking for the most recent analysis step
            if not current_step:  # noqa: SIM102
                # Find the last analysis step
                if analysis_steps:
                    current_step = analysis_steps[-1]

            if current_step:
                sub_event = {
                    "action": action,
                    "step": event.get("step", ""),
                    "status": event.get("status", ""),
                    "context": event.get("context", ""),
                    "target": event.get("target", ""),
                    "point": event.get("point", ""),
                    "url": event.get("url", ""),
                    "input_tokens": event.get("input_tokens", 0),
                    "output_tokens": event.get("output_tokens", 0),
                    "cost": event.get("cost", 0.0),
                    "result": event.get("result", ""),
                    "reason": event.get("reason", ""),
                }
                current_step["sub_events"].append(sub_event)

        # Track detect-pagination sub-events
        elif event_type == "detect-pagination":
            if action == "llm-completion":  # noqa: SIM102
                # Only process non-pending events
                if event.get("status") != "pending":
                    # Add to current pagination detection attempt
                    if current_pagination_detection:
                        current_pagination_detection["llm_calls"].append({
                            "status": event.get("status", ""),
                            "input_tokens": event.get("input_tokens", 0),
                            "output_tokens": event.get("output_tokens", 0),
                            "cost": event.get("cost", 0.0),
                            "result": event.get("result", ""),
                            "reason": event.get("reason", ""),
                        })
                    elif pagination_detections:
                        # Fallback: add to most recent if no current attempt
                        if "llm_calls" not in pagination_detections[-1]:
                            pagination_detections[-1]["llm_calls"] = []
                        pagination_detections[-1]["llm_calls"].append({
                            "status": event.get("status", ""),
                            "input_tokens": event.get("input_tokens", 0),
                            "output_tokens": event.get("output_tokens", 0),
                            "cost": event.get("cost", 0.0),
                            "result": event.get("result", ""),
                            "reason": event.get("reason", ""),
                        })

        # Track code generation sub-events
        elif event_type == "code-generation":
            if action == "llm-completion":
                # Only process non-pending events
                if event.get("status") != "pending":
                    llm_attempts = [c for c in code_generations if "llm_completion" in c]
                    # Create new attempt or update existing one
                    attempt_number = len(llm_attempts) + 1
                    code_generations.append({
                        "attempt_number": attempt_number,
                        "llm_completion": {
                            "status": event.get("status", ""),
                            "input_tokens": event.get("input_tokens", 0),
                            "output_tokens": event.get("output_tokens", 0),
                            "cost": event.get("cost", 0.0),
                            "result": event.get("result", ""),
                            "reason": event.get("reason", ""),
                        },
                        "validation": None,
                    })
            elif action == "llm-completion:validation":  # noqa: SIM102
                # Add validation to the most recent attempt
                if code_generations:
                    last_attempt = code_generations[-1]
                    last_attempt["validation"] = {"status": event.get("status", ""), "reason": event.get("reason", "")}

    # Handle any unfinished pagination detection attempt
    if current_pagination_detection:
        pagination_detections.append(current_pagination_detection)

    # Sort analysis steps by step count
    analysis_steps.sort(key=lambda x: x["step_count"])

    # Calculate summary statistics
    total_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0

    # Count tokens and costs from all LLM calls
    for step in analysis_steps:
        for sub_event in step["sub_events"]:
            total_cost += sub_event.get("cost", 0.0)
            total_input_tokens += sub_event.get("input_tokens", 0)
            total_output_tokens += sub_event.get("output_tokens", 0)

    for pagination in pagination_detections:
        for llm_call in pagination.get("llm_calls", []):
            total_cost += llm_call.get("cost", 0.0)
            total_input_tokens += llm_call.get("input_tokens", 0)
            total_output_tokens += llm_call.get("output_tokens", 0)

    for code_gen in code_generations:
        if code_gen.get("llm_completion"):
            total_cost += code_gen["llm_completion"].get("cost", 0.0)
            total_input_tokens += code_gen["llm_completion"].get("input_tokens", 0)
            total_output_tokens += code_gen["llm_completion"].get("output_tokens", 0)

    # Set up Jinja2 environment
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    # Add custom filters
    def tojson(value, indent=None):
        return json.dumps(value, indent=indent, ensure_ascii=False)

    def format_cost(value):
        return f"${value:.4f}"

    env.filters["tojson"] = tojson
    env.filters["format_cost"] = format_cost

    # Calculate additional metrics
    final_result = None
    final_pagination_strategy = None
    code_generation_success = False
    analysis_duration = "Unknown"

    # Find final result
    if analysis_end:  # noqa: SIM102
        if analysis_end.get("status") == "success":
            final_result = {"api_url": analysis_end.get("relevant_api_call", "")}

    # Find successful pagination strategy
    for pagination in pagination_detections:
        if pagination.get("status") == "success" and pagination.get("strategy"):
            final_pagination_strategy = pagination
            break

    # Check code generation success
    for code_gen in code_generations:
        if code_gen.get("status") == "success" or (
            code_gen.get("validation") and code_gen["validation"].get("status") == "success"
        ):
            code_generation_success = True
            break

    # Calculate duration
    if analysis_begin and analysis_end:
        start_time = analysis_begin.get("timestamp", "")
        end_time = analysis_end.get("timestamp", "")
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration = end_dt - start_dt
                analysis_duration = f"{duration.total_seconds():.1f}s"
            except:  # noqa: E722
                analysis_duration = "Unknown"

    return env.get_template("simple_report.html").render(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        url=url,
        query=query,
        analysis_begin=analysis_begin,
        analysis_end=analysis_end,
        analysis_steps=analysis_steps,
        pagination_detections=pagination_detections,
        code_generations=code_generations,
        total_cost=total_cost,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_steps=len(analysis_steps),
        final_result=final_result,
        final_pagination_strategy=final_pagination_strategy,
        code_generation_success=code_generation_success,
        analysis_duration=analysis_duration,
    )
