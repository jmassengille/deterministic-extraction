# Configuration

All configuration is done through environment variables in a `.env` file.

## Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |

## Domain Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EXTRACTION_SCHEMA` | `extraction` | Schema file name (without .yaml) in `config/schemas/` |
| `PROMPT_DIRECTORY` | `default` | Subdirectory in `config/prompts/` for domain prompts |
| `PROMPT_VERSION` | `universal` | Prompt version identifier |
| `DEFAULT_OUTPUT_FORMAT` | `json` | Default output format when not specified |

## LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL_ASYNC` | `main` | Model for async extraction: `main`, `mini`, `nano` |
| `LLM_MODEL_EXTRACTION` | `main` | Model for main extraction |
| `LLM_REASONING_EFFORT` | `high` | GPT-5 reasoning: `minimal`, `low`, `medium`, `high` |
| `LLM_VERBOSITY` | `medium` | Response verbosity: `low`, `medium`, `high` |
| `LLM_MAX_OUTPUT_TOKENS` | `32768` | Maximum tokens in LLM response |
| `EXTRACTION_MODE` | `single` | Extraction mode: `single` or `multi` (multi-pass) |

## Hardcoded Settings

These values are set in code and not configurable via environment variables:

| Setting | Value | Location |
|---------|-------|----------|
| Max concurrent LLM calls | `5` | `settings.py:55` |
| LLM request timeout | `600s` | `settings.py:41` |
| Output directory | `Data/artifacts` | `settings.py:59` |
| Temp directory | `Data/temp` | `settings.py:60` |

## Example .env File

```env
# Required
OPENAI_API_KEY=sk-...

# Domain (customize for your use case)
EXTRACTION_SCHEMA=invoice_extraction
PROMPT_DIRECTORY=invoice
DEFAULT_OUTPUT_FORMAT=json

# LLM (adjust based on accuracy vs speed needs)
LLM_MODEL_EXTRACTION=main
LLM_REASONING_EFFORT=high
```

## Adding a New Domain

1. Create schema file:
   ```
   src/backend/config/schemas/mydomain_extraction.yaml
   ```

2. Create prompt directory:
   ```
   src/backend/config/prompts/mydomain/
   ```

3. Set environment variables:
   ```env
   EXTRACTION_SCHEMA=mydomain_extraction
   PROMPT_DIRECTORY=mydomain
   ```

## Schema Requirements

Schemas must be OpenAI function calling format with:
- `"additionalProperties": false`
- `"strict": true`
- All properties in `required` array

See existing schemas in `src/backend/config/schemas/` for examples.
