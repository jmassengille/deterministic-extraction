# Document Processing Template: Ready for Use

**Date**: 2025-12-09
**Status**: COMPLETE
**Phase**: All phases (P0-P3) + Documentation cleanup

---

## Summary

Domain-agnostic document processing pipeline. Configure via environment variables, schemas, and prompts. No code changes required for new domains.

---

## Completed Changes by Phase

### Phase P0: Unblock Template Usage

| File | Changes |
|------|---------|
| `src/backend/llm/client.py` | Renamed `extract_calibration_specs` -> `extract_structured_data` with parameterized schema |
| `src/backend/llm/client.py` | Renamed `extract_calibration_specs_from_image` -> `extract_structured_data_from_image` |
| `src/backend/llm/client.py` | Added `EXTRACTION_SCHEMA` config, dynamic schema loading |
| `src/web/routes/upload.py` | Dynamic format validation from `SerializerFactory.get_available_formats()` |
| `src/web/routes/jobs.py` | Generic `FormatInfo` model, unified `_download_format()` handler |

### Phase P1: Enable New Domains

| File | Changes |
|------|---------|
| `src/web/jobs/schemas.py` | Renamed stages: `LOADING_DOCUMENT`, `ANALYZING_STRUCTURE`, `EXTRACTING_REGIONS`, `PROCESSING_DATA`, `GENERATING_OUTPUT` |
| `src/web/jobs/schemas.py` | Unified `output_paths: Dict[str, Any]` replacing `msf_path` and `acc_paths` |
| `src/backend/config/settings.py` | Removed `ENABLE_ACC_OUTPUT`, `ACC_DEFAULT_INTERVALS`, `PROMPT_DIRECTORIES` |
| `src/backend/config/settings.py` | Added `EXTRACTION_SCHEMA`, `PROMPT_DIRECTORY` environment variables |
| `src/web/services/worker.py` | Removed `ACC_INTERVAL_SUFFIX_MAP`, replaced `_extract_acc_paths` with `_build_output_paths` |

### Phase P2: Clean Abstractions

| File | Changes |
|------|---------|
| `src/backend/llm/multipass_extractor.py` | Removed `INSTRUMENT_PROMPT_MAP`, replaced with configurable `PROMPT_DIRECTORY` |
| `src/backend/llm/multipass_extractor.py` | Updated docstrings to be domain-agnostic |
| `src/backend/llm/async_extractor.py` | Updated docstring to be domain-agnostic |
| `src/backend/config/prompts/prompt_loader.py` | Removed ACC electrical domain routing |

### Phase P3: Frontend Polish

| File | Changes |
|------|---------|
| `src/web/frontend/src/utils/constants.js` | Generic stage names: `LOADING_DOCUMENT`, `ANALYZING_STRUCTURE`, etc. |
| `src/web/frontend/src/services/api.js` | Default format changed from `msf` to `json`, `interval` param renamed to `key` |
| `src/web/frontend/src/pages/JobDetail.jsx` | Generic `output_paths` display, `document_info` metadata |

### Documentation Cleanup

| Action | Details |
|--------|---------|
| Removed | `docs/.archive-2025-11/`, `docs/.archive-2025-12/`, `docs/plans/`, `docs/architecture/` |
| Removed | `docs/index.md`, `docs/CLI.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md` |
| Rewritten | `README.md` - minimal setup guide |
| Updated | `docs/API.md` - accurate endpoint documentation |
| Updated | `docs/CONFIGURATION.md` - verified environment variables |

---

## Configuration for New Domains

### Environment Variables

```bash
# Extraction schema (config/schemas/{name}.yaml)
EXTRACTION_SCHEMA=invoice_extraction

# Prompt directory (config/prompts/{directory}/)
PROMPT_DIRECTORY=invoice

# Default output format
DEFAULT_OUTPUT_FORMAT=json
```

### Adding a New Domain

1. **Create extraction schema**: `config/schemas/{domain}_extraction.yaml`
   - Must include `"additionalProperties": false`, `"strict": true`
   - All properties in `required` array

2. **Create prompts**: `config/prompts/{domain}/`
   - System and user prompt templates in YAML

3. **Create serializer** (optional): `serializers/{format}.py`
   ```python
   @register_serializer("myformat")
   class MyFormatSerializer(FormatSerializer):
       def serialize(self, data: dict) -> str:
           ...
   ```

4. **Configure environment**: Set `EXTRACTION_SCHEMA` and `PROMPT_DIRECTORY`

---

## Architecture Overview

```
Document Processing Template
├── src/backend/
│   ├── config/
│   │   ├── prompts/{domain}/    # Domain-specific prompts
│   │   ├── schemas/             # Function calling schemas
│   │   └── settings.py          # Environment-based config
│   ├── llm/
│   │   ├── client.py            # GPT-5 Responses API client
│   │   └── *_extractor.py       # Extraction orchestrators
│   ├── pdf/                     # Table detection & cropping
│   └── serializers/             # Pluggable output formats
└── src/web/
    ├── routes/                  # REST API endpoints
    ├── jobs/                    # Job state machine
    └── frontend/                # React UI
```

---

## Preserved Capabilities

- Batch PDF upload with queue management
- Async job processing with retry logic
- SSE-based progress streaming
- LLM extraction with function calling (schema-driven)
- Multi-pass extraction pipeline (configurable via prompts)
- Pluggable output serialization framework
- React frontend for upload/status/review workflows
- SQLite job persistence
- File storage with cleanup scheduling

---

## Files Modified (12 total)

| File | Type |
|------|------|
| `src/backend/llm/client.py` | Backend |
| `src/backend/llm/async_extractor.py` | Backend |
| `src/backend/llm/multipass_extractor.py` | Backend |
| `src/backend/config/settings.py` | Backend |
| `src/backend/config/prompts/prompt_loader.py` | Backend |
| `src/web/routes/upload.py` | Web |
| `src/web/routes/jobs.py` | Web |
| `src/web/jobs/schemas.py` | Web |
| `src/web/services/worker.py` | Web |
| `src/web/frontend/src/utils/constants.js` | Frontend |
| `src/web/frontend/src/services/api.js` | Frontend |
| `src/web/frontend/src/pages/JobDetail.jsx` | Frontend |

---

## Next Steps for New Projects

1. Fork this template repository
2. Create domain-specific schemas and prompts
3. Implement serializers for target output formats
4. Configure environment variables
5. Deploy

No code changes required for basic domain adaptation.
