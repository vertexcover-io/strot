# Project: Strot

## Tech Stack & Tooling

- **Language**: Python 3.10+
- **Package Manager**: `uv` (use `uv add <dependency>`, `uv run <script>`)
- **Linting**: ruff + mypy

## Systematic File Naming

Format: `YYYY-MM-DD-[001-999]-[category]-[four-word-summary].md`
Folder: `docs/work/`
Categories: `bug` | `feature` | `task` | `research` | `learnings`

Examples:

- `2025-07-18-001-feature-html-response-preprocessing.md`
- `2025-07-18-002-bug-cursor-value-extraction.md`

## Communication Style

- **Concise**: No fluff, direct responses
- **Evidence-based**: Show, don't just tell
- **Contextual**: Reference past learnings from `docs/work/`

## Planning Protocol

1. **Context Gathering**: Check `docs/work/` for relevant past decisions
2. **Assumption Documentation**: Explicit assumptions in plan files
3. **Execution Gate**: Only proceed after planning is complete

---

When context drops below 30%:

1. Document every decision made
2. List what failed (with code snippets)
3. Note what worked brilliantly
4. Write handoff notes for next session

Use the `Systematic File Naming` given above.
