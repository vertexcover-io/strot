import json
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

from strot.logging import LogLevel, get_logger, setup_logging

app = App(name="stroteval", help_flags=[], version_flags=[])

setup_logging(overrides={"httpx": LogLevel.WARNING})


@app.default
async def run(
    *,
    file: Annotated[
        Path | None,
        Parameter(
            name=("-f", "--file"),
            validator=validators.Path(exists=True, dir_okay=False, ext=["json", "jsonl"]),
        ),
    ] = None,
) -> None:
    """
    Evaluate multiple job-based or task-based inputs from a file or stdin.

    Args:
        file: Path to the JSON/JSONL file. If not provided, reads from stdin.
    """
    if file:
        content = file.read_text()
        source_name = str(file)
        is_jsonl = file.suffix == ".jsonl"
    else:
        if sys.stdin.isatty():
            app.help_print()
            return

        content = sys.stdin.read()
        source_name = "stdin"
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        is_jsonl = len(lines) > 1 and all(line.startswith("{") for line in lines)

    from eval.airtable import AirtableClient
    from eval.inputs import JobBasedInput, TaskBasedInput
    from strot.type_adapter import TypeAdapter

    inputs_adapter = TypeAdapter(list[TaskBasedInput | JobBasedInput])

    if is_jsonl:
        inputs = inputs_adapter.validate_python([
            json.loads(line) for line in content.strip().split("\n") if line.strip()
        ])
    else:
        inputs = inputs_adapter.validate_json(content)

    print(f"📋 Loaded {len(inputs)} evaluation inputs from {source_name}")

    from eval.evaluator import JobEvaluator, TaskEvaluator

    logger = get_logger()
    airtable_client = AirtableClient(logger=logger)
    job_evaluator = JobEvaluator(airtable_client=airtable_client, logger=logger)
    separate_evaluator = TaskEvaluator(airtable_client=airtable_client, logger=logger)

    for i, input_obj in enumerate(inputs, 1):
        if isinstance(input_obj, JobBasedInput):
            evaluator = job_evaluator
        elif isinstance(input_obj, TaskBasedInput):
            evaluator = separate_evaluator
        else:
            print(f"❌ [{i}/{len(inputs)}] Unknown input type: {type(input_obj)}")
            continue

        print(f"🔄 [{i}/{len(inputs)}] Processing {input_obj.type}: {input_obj.identifier}")

        try:
            await evaluator.evaluate(input_obj)
            print(f"✅ [{i}/{len(inputs)}] Completed {input_obj.type}: {input_obj.identifier}")
        except Exception as e:
            print(f"❌ [{i}/{len(inputs)}] Failed {input_obj.type}: {input_obj.identifier} - {e!s}")
            continue

    print(f"🎉 Batch processing completed from {source_name}")


if __name__ == "__main__":
    app()
