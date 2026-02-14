# JSON Logs Viewer

A terminal-based JSON log viewer built with [Textual](https://textual.textualize.io/).

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