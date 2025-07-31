import json
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

from eval.evaluator import Evaluator, ExistingJobInput, NewJobInput
from strot.type_adapter import TypeAdapter

evaluator = Evaluator()
app = App(name="strot-eval")


@app.command
async def new(*, input: Annotated[NewJobInput, Parameter(name="*", negative_iterable=[])]) -> None:
    """
    Create a new job and evaluate it.
    """
    await evaluator.evaluate(input)


@app.command
async def existing(*, input: Annotated[ExistingJobInput, Parameter(name="*", negative_iterable=[])]) -> None:
    """
    Evaluate an existing job.
    """
    await evaluator.evaluate(input)


@app.command
async def from_file(
    file: Annotated[Path, Parameter(validator=validators.Path(exists=True, dir_okay=False, ext=["json", "jsonl"]))],
) -> None:
    """
    Evaluate multiple (existing or new) jobs from a JSON/JSONL file.

    Args:
        file: Path to the JSON/JSONL file.
    """

    content = file.read_text()
    inputs_adapter = TypeAdapter(list[NewJobInput | ExistingJobInput])

    if file.suffix == ".jsonl":
        inputs = inputs_adapter.validate_python([
            json.loads(line) for line in content.strip().split("\n") if line.strip()
        ])
    else:
        inputs = inputs_adapter.validate_json(content)

    print(f"📋 Loaded {len(inputs)} evaluation inputs from {file}")

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

    print(f"🎉 Batch processing completed for {file}")


if __name__ == "__main__":
    app()
