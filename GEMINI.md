## Project Instructions
- **Project Goal:** A multi-agent system designed to reduce the "administrative orbit" of physicians (referrals, labs, documentation).
- **Core Architecture:** A "Society of Agents" consisting of three layers: Substrate (wiki maintenance), Workflow (task execution), and Meta (orchestration and safety).
- **Wiki Pattern:** Every agent is grounded in a "LLM Wiki"-- a knowledge base of a specific doctor's accumulated reasoning and clinical preferences.
- **Privacy Model:** Patient data is pulled into a session, used for the workflow, and then discarded to avoid the regulatory burden of storing sensitive information.

## LLM Configuration
- **Backends:** Supports both Anthropic (default) and Gemini.
- **CLI Toggle:** Use `--llm [anthropic|gemini]` to switch providers.
- **Model Selection:** Use `--model [model_name]` to override the default model.
- **SDKs:** Uses `anthropic` for Claude and `google-genai` for Gemini.
- **Default Models:** 
    - Anthropic: `claude-opus-4-7`
    - Gemini: `gemini-3.1-flash-lite`

## Error Handling
- Default to letting code fail fast rather than trying to recover silently.
- Do not suppress exceptions unless explicitly instructed.
- When expectations are violated, use `assert` statements or raise clear errors immediately.
- Prefer early failure over hidden fallback behavior.

## Assumptions
- For every non-trivial method, explicitly identify its assumptions before or while implementing it.
- Validate important assumptions in code.
- Add tests that cover those assumptions, especially edge cases and failure cases.
- Do not leave critical assumptions implicit.

## Code Reuse and Organization
- Always look for opportunities to reuse existing code before writing new code.
- Prefer general-purpose helper functions over one-off duplicated logic.
- If functionality is likely to be reused across files, put it in a central utility module.
- Avoid copy-pasting logic when a shared helper would make the code clearer.
- Optimize for maintainability and consistency across the codebase.

## General Implementation Style
- Write small, composable functions with clear responsibilities.
- Prefer explicit behavior over clever abstractions.
- Make invalid states obvious and hard to ignore.
- Keep code straightforward enough that assumptions and failure modes are easy to inspect.

## Simplicity
- Prefer the simplest implementation that satisfies the requirements.
- Do not introduce abstractions unless they clearly reduce duplication or
complexity.
- Avoid premature optimization.
- Avoid unnecessary classes, configuration layers, or indirection.
- Prefer straightforward procedural logic unless an abstraction clearly
improves clarity.

## File organization
- Each file should have a clear responsibility.
- Avoid files longer than ~500 lines, when possible.
- Shared utilities belong in a central utilities module.
- Avoid circular imports.

## Documentation
- Every module should have a top-level description.
- Every non-trivial function should explain: what it does, its assumptions, its inputs and outputs