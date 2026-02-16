# JSON Logs Viewer

An interactive terminal JSONL log viewer built with
[Textual](https://textual.textualize.io/).

## Features

- Fast keyboard-first navigation (`j`/`k`, `g`/`G`, `h`/`l`).
- Structured filtering with field queries and boolean logic:
  `level:error AND (service:api OR service:web) NOT debug`.
- Case-sensitive filtering toggle.
- Highlight mode to dim non-matching entries instead of hiding them.
- Optional soft-wrap mode for long JSON lines.
- Status bar with file name, total logs, filtered count, and quick toggles.
- Search/query history tracking.
- Built-in help modal (`?`) with available features.

## Usage

```bash
uv run json-logs-viewer <file.jsonl>
```

## Development

Install dev dependencies:

```bash
uv add --dev textual-dev
```

Run with live CSS reloading and dev console:

```bash
uv run textual run --dev -c json-logs-viewer test_files/sample.jsonl
```

Serve in the browser:

```bash
uv run textual serve "json-logs-viewer test_files/sample.jsonl"
```