import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

__all__ = ("generate_report",)


def generate_report(jsonl_content: str) -> str:  # noqa: C901
    """
    Generate an HTML report from JSONL log content with nested JSON structure.

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
            # Extract the actual log data from the "message" field
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

    # Group events by analysis steps
    analysis_steps = []
    current_step = None
    code_generation_attempts = []
    strategy_determination = None
    url = ""
    query = ""
    in_strategy_determination = False

    # Try to find URL and query from any event that has them
    for event in events:
        if not url and event.get("url"):
            url = event.get("url", "")
        if not query and event.get("query"):
            query = event.get("query", "")
        if url and query:
            break

    for event in events:
        event_type = event.get("event", "unknown")
        action = event.get("action", "")

        # Track analysis steps
        if event_type == "analysis" and action == "run-step":
            step_count = event.get("step_count", 0)
            if current_step is None or current_step["step_count"] != step_count:
                current_step = {
                    "step_count": step_count,
                    "status": event.get("status", ""),
                    "llm_calls": [],
                    "actions": [],
                    "screenshots": [],
                    "matching_results": [],
                }
                analysis_steps.append(current_step)

        # Check if we're entering strategy determination phase
        elif event_type == "determine-strategy":
            in_strategy_determination = True
            if strategy_determination is None:
                strategy_determination = {"attempts": [], "final_strategy": None}

            if action == "build-strategy-info":
                strategy_determination["final_strategy"] = {
                    "strategy": event.get("strategy", ""),
                    "page_key": event.get("page_key", ""),
                    "offset_key": event.get("offset_key", ""),
                    "limit_key": event.get("limit_key", ""),
                    "cursor_key": event.get("cursor_key", ""),
                    "first_cursor": event.get("first_cursor", ""),
                    "base_offset": event.get("base_offset", 0),
                    "pagination_patterns": event.get("pagination_patterns", 0),
                }
            elif action == "run-step":
                strategy_determination["attempts"].append({
                    "step_count": event.get("step_count", 0),
                    "status": event.get("status", ""),
                    "method": event.get("method", ""),
                    "url": event.get("url", ""),
                    "queries": event.get("queries", {}),
                    "data": event.get("data", {}),
                    "exception": event.get("exception", ""),
                })

        # Track code generation (this marks end of strategy determination)
        elif event_type == "code-generation":
            in_strategy_determination = False
            if action == "llm-completion":
                if event.get("status") == "pending":
                    # Create a new code generation attempt
                    code_generation_attempts.append({
                        "llm_completion": {"status": "pending", "input_tokens": 0, "output_tokens": 0, "exception": ""},
                        "validation": None,
                        "attempt_number": len(code_generation_attempts) + 1,
                    })
                else:
                    # Update the last attempt with completion data
                    if code_generation_attempts:
                        last_attempt = code_generation_attempts[-1]
                        last_attempt["llm_completion"]["status"] = event.get("status", "")
                        last_attempt["llm_completion"]["input_tokens"] = event.get("input_tokens", 0)
                        last_attempt["llm_completion"]["output_tokens"] = event.get("output_tokens", 0)
                        last_attempt["llm_completion"]["exception"] = event.get("exception", "")
                    else:
                        # No pending attempt, create a new one
                        code_generation_attempts.append({
                            "llm_completion": {
                                "status": event.get("status", ""),
                                "input_tokens": event.get("input_tokens", 0),
                                "output_tokens": event.get("output_tokens", 0),
                                "exception": event.get("exception", ""),
                            },
                            "validation": None,
                            "attempt_number": len(code_generation_attempts) + 1,
                        })
            elif action == "validation":
                if code_generation_attempts:
                    last_attempt = code_generation_attempts[-1]
                    last_attempt["validation"] = {
                        "status": event.get("status", ""),
                        "exception": event.get("exception", ""),
                    }
                else:
                    # No LLM completion, create a new attempt with just validation
                    code_generation_attempts.append({
                        "llm_completion": None,
                        "validation": {"status": event.get("status", ""), "exception": event.get("exception", "")},
                        "attempt_number": len(code_generation_attempts) + 1,
                    })

        # Track LLM completions and actions based on context
        elif event_type == "run-step":
            if in_strategy_determination:
                # This is part of strategy determination, create a separate step
                if action == "llm-completion":
                    # Find the last strategy step or create a new one
                    last_attempt = (
                        strategy_determination["attempts"][-1] if strategy_determination["attempts"] else None
                    )
                    if last_attempt:
                        if "llm_calls" not in last_attempt:
                            last_attempt["llm_calls"] = []

                        # Handle pending vs completed LLM events
                        if event.get("status") == "pending":
                            # Store pending event data
                            llm_call = {
                                "status": "pending",
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "cost": 0.0,
                                "result": "",
                                "exception": "",
                            }
                            last_attempt["llm_calls"].append(llm_call)
                        else:
                            # Find the last pending LLM call and update it
                            for i in range(len(last_attempt["llm_calls"]) - 1, -1, -1):
                                if last_attempt["llm_calls"][i].get("status") == "pending":
                                    # Update the existing pending event with completion data
                                    last_attempt["llm_calls"][i]["status"] = event.get("status", "")
                                    last_attempt["llm_calls"][i]["input_tokens"] = event.get("input_tokens", 0)
                                    last_attempt["llm_calls"][i]["output_tokens"] = event.get("output_tokens", 0)
                                    last_attempt["llm_calls"][i]["cost"] = event.get("cost", 0.0)
                                    last_attempt["llm_calls"][i]["result"] = event.get("result", "")
                                    last_attempt["llm_calls"][i]["exception"] = event.get("exception", "")
                                    break
                            else:
                                # No pending event found, create a new one
                                llm_call = {
                                    "status": event.get("status", ""),
                                    "input_tokens": event.get("input_tokens", 0),
                                    "output_tokens": event.get("output_tokens", 0),
                                    "cost": event.get("cost", 0.0),
                                    "result": event.get("result", ""),
                                    "exception": event.get("exception", ""),
                                }
                                last_attempt["llm_calls"].append(llm_call)

                elif "step" in event:
                    step_action = {
                        "step_type": event.get("step", ""),
                        "context": event.get("context", ""),
                        "target_selector": event.get("target_selector", ""),
                        "status": event.get("status", ""),
                    }
                    # Find the last strategy step or create a new one
                    last_attempt = (
                        strategy_determination["attempts"][-1] if strategy_determination["attempts"] else None
                    )
                    if last_attempt:
                        if "actions" not in last_attempt:
                            last_attempt["actions"] = []
                        last_attempt["actions"].append(step_action)

                elif action == "matching":
                    # Find the last strategy step or create a new one
                    last_attempt = (
                        strategy_determination["attempts"][-1] if strategy_determination["attempts"] else None
                    )
                    if last_attempt:
                        if "matching_results" not in last_attempt:
                            last_attempt["matching_results"] = []

                        # Handle pending vs completed matching events
                        if event.get("status") == "pending":
                            # Store pending event data
                            matching_result = {
                                "url": event.get("url", ""),
                                "score": 0.0,
                                "sections": event.get("sections", []),
                                "status": "pending",
                            }
                            last_attempt["matching_results"].append(matching_result)
                        else:
                            # Find the most recent pending matching event and update it
                            # The completed event doesn't have URL, so we match by finding the last pending event
                            for i in range(len(last_attempt["matching_results"]) - 1, -1, -1):
                                if last_attempt["matching_results"][i].get("status") == "pending":
                                    # Update the existing pending event with completion data
                                    last_attempt["matching_results"][i]["score"] = event.get("score", 0.0)
                                    last_attempt["matching_results"][i]["status"] = event.get("status", "")
                                    break
                            else:
                                # No pending event found, create a new one (shouldn't happen)
                                matching_result = {
                                    "url": event.get("url", ""),
                                    "score": event.get("score", 0.0),
                                    "sections": event.get("sections", []),
                                    "status": event.get("status", ""),
                                }
                                last_attempt["matching_results"].append(matching_result)
            else:
                # This is part of main analysis steps
                if action == "llm-completion":
                    if current_step:
                        # Handle pending vs completed LLM events
                        if event.get("status") == "pending":
                            # Store pending event data
                            llm_call = {
                                "status": "pending",
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "cost": 0.0,
                                "result": "",
                                "exception": "",
                            }
                            current_step["llm_calls"].append(llm_call)
                        else:
                            # Find the last pending LLM call and update it
                            for i in range(len(current_step["llm_calls"]) - 1, -1, -1):
                                if current_step["llm_calls"][i].get("status") == "pending":
                                    # Update the existing pending event with completion data
                                    current_step["llm_calls"][i]["status"] = event.get("status", "")
                                    current_step["llm_calls"][i]["input_tokens"] = event.get("input_tokens", 0)
                                    current_step["llm_calls"][i]["output_tokens"] = event.get("output_tokens", 0)
                                    current_step["llm_calls"][i]["cost"] = event.get("cost", 0.0)
                                    current_step["llm_calls"][i]["result"] = event.get("result", "")
                                    current_step["llm_calls"][i]["exception"] = event.get("exception", "")
                                    break
                            else:
                                # No pending event found, create a new one
                                llm_call = {
                                    "status": event.get("status", ""),
                                    "input_tokens": event.get("input_tokens", 0),
                                    "output_tokens": event.get("output_tokens", 0),
                                    "cost": event.get("cost", 0.0),
                                    "result": event.get("result", ""),
                                    "exception": event.get("exception", ""),
                                }
                                current_step["llm_calls"].append(llm_call)

                elif "step" in event:
                    step_action = {
                        "step_type": event.get("step", ""),
                        "context": event.get("context", ""),
                        "target_selector": event.get("target_selector", ""),
                        "status": event.get("status", ""),
                    }
                    if current_step:
                        current_step["actions"].append(step_action)

                elif action == "matching":  # noqa: SIM102
                    if current_step:
                        # Handle pending vs completed matching events
                        if event.get("status") == "pending":
                            # Store pending event data
                            matching_result = {
                                "url": event.get("url", ""),
                                "score": 0.0,
                                "sections": event.get("sections", []),
                                "status": "pending",
                            }
                            current_step["matching_results"].append(matching_result)
                        else:
                            # Find the most recent pending matching event and update it
                            # The completed event doesn't have URL, so we match by finding the last pending event
                            for i in range(len(current_step["matching_results"]) - 1, -1, -1):
                                if current_step["matching_results"][i].get("status") == "pending":
                                    # Update the existing pending event with completion data
                                    current_step["matching_results"][i]["score"] = event.get("score", 0.0)
                                    current_step["matching_results"][i]["status"] = event.get("status", "")
                                    break
                            else:
                                # No pending event found, create a new one (shouldn't happen)
                                matching_result = {
                                    "url": event.get("url", ""),
                                    "score": event.get("score", 0.0),
                                    "sections": event.get("sections", []),
                                    "status": event.get("status", ""),
                                }
                                current_step["matching_results"].append(matching_result)

        # Track matching results from skip-similar-content
        elif event_type == "skip-similar-content" and action == "matching":
            if in_strategy_determination:
                last_attempt = strategy_determination["attempts"][-1] if strategy_determination["attempts"] else None
                if last_attempt:
                    if "matching_results" not in last_attempt:
                        last_attempt["matching_results"] = []

                    # Handle pending vs completed matching events
                    if event.get("status") == "pending":
                        # Store pending event data
                        matching_result = {
                            "url": event.get("url", ""),
                            "score": 0.0,
                            "sections": event.get("sections", []),
                            "status": "pending",
                        }
                        last_attempt["matching_results"].append(matching_result)
                    else:
                        # Find the corresponding pending event and update it
                        match_url = event.get("url", "")
                        for existing_match in last_attempt["matching_results"]:
                            if existing_match.get("url") == match_url and existing_match.get("status") == "pending":
                                # Update the existing pending event with completion data
                                existing_match["score"] = event.get("score", 0.0)
                                existing_match["status"] = event.get("status", "")
                                break
                        else:
                            # No pending event found, create a new one
                            matching_result = {
                                "url": match_url,
                                "score": event.get("score", 0.0),
                                "sections": event.get("sections", []),
                                "status": event.get("status", ""),
                            }
                            last_attempt["matching_results"].append(matching_result)
            elif current_step:
                # Handle pending vs completed matching events
                if event.get("status") == "pending":
                    # Store pending event data
                    matching_result = {
                        "url": event.get("url", ""),
                        "score": 0.0,
                        "sections": event.get("sections", []),
                        "status": "pending",
                    }
                    current_step["matching_results"].append(matching_result)
                else:
                    # Find the most recent pending matching event and update it
                    # The completed event doesn't have URL, so we match by finding the last pending event
                    for i in range(len(current_step["matching_results"]) - 1, -1, -1):
                        if current_step["matching_results"][i].get("status") == "pending":
                            # Update the existing pending event with completion data
                            current_step["matching_results"][i]["score"] = event.get("score", 0.0)
                            current_step["matching_results"][i]["status"] = event.get("status", "")
                            break
                    else:
                        # No pending event found, create a new one (shouldn't happen)
                        matching_result = {
                            "url": event.get("url", ""),
                            "score": event.get("score", 0.0),
                            "sections": event.get("sections", []),
                            "status": event.get("status", ""),
                        }
                        current_step["matching_results"].append(matching_result)

    # Calculate summary statistics
    total_cost = sum(call["cost"] for step in analysis_steps for call in step["llm_calls"] if call.get("cost"))

    total_tokens = sum(
        call["input_tokens"] + call["output_tokens"] for step in analysis_steps for call in step["llm_calls"]
    )

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
    pagination_strategy = None
    code_generation_success = False
    analysis_duration = "Unknown"

    # Find final result
    for event in events:
        if event.get("event") == "analysis" and event.get("action") == "end":
            if event.get("status") == "success":
                final_result = {"api_url": event.get("relevant_api_call", "")}
            break

    # Find pagination strategy
    if strategy_determination and strategy_determination.get("final_strategy"):
        pagination_strategy = strategy_determination["final_strategy"]

    # Check code generation success
    for attempt in code_generation_attempts:
        if attempt.get("validation") and attempt["validation"].get("status") == "success":
            code_generation_success = True
            break

    # Calculate duration
    if events:
        start_time = events[0].get("timestamp", "")
        end_time = events[-1].get("timestamp", "")
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration = end_dt - start_dt
                analysis_duration = f"{duration.total_seconds():.1f}s"
            except:  # noqa: E722
                analysis_duration = "Unknown"

    return env.get_template("report.html").render(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        url=url,
        query=query,
        analysis_steps=analysis_steps,
        strategy_determination=strategy_determination,
        code_generation_attempts=code_generation_attempts,
        total_cost=total_cost,
        total_tokens=total_tokens,
        total_steps=len(analysis_steps),
        final_result=final_result,
        pagination_strategy=pagination_strategy,
        code_generation_success=code_generation_success,
        analysis_duration=analysis_duration,
    )
