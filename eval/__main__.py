import json
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

app = App(name="stroteval", help_flags=[], version_flags=[])


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
    Evaluate multiple (existing or new) jobs from a file or stdin.

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

    from eval.types import ExistingJobInput, NewJobInput
    from strot.type_adapter import TypeAdapter

    inputs_adapter = TypeAdapter(list[ExistingJobInput | NewJobInput])

    if is_jsonl:
        inputs = inputs_adapter.validate_python([
            json.loads(line) for line in content.strip().split("\n") if line.strip()
        ])
    else:
        inputs = inputs_adapter.validate_json(content)

    print(f"📋 Loaded {len(inputs)} evaluation inputs from {source_name}")

    from eval.evaluator import Evaluator

    evaluator = Evaluator()
    for i, input_obj in enumerate(inputs, 1):
        job_type = "new job" if isinstance(input_obj, NewJobInput) else "existing job"
        identifier = getattr(input_obj, "site_url", input_obj.job_id)

        print(f"🔄 [{i}/{len(inputs)}] Processing {job_type}: {identifier}")

        try:
            await evaluator.evaluate(input_obj)
            print(f"✅ [{i}/{len(inputs)}] Completed: {identifier}")
        except Exception as e:
            print(f"❌ [{i}/{len(inputs)}] Failed: {identifier} - {e!s}")
            continue

    print(f"🎉 Batch processing completed from {source_name}")


if __name__ == "__main__":
    app()
