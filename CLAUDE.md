# Document Processing Template - Project Configuration

**Mission**: Batch document processing framework with LLM-powered extraction and pluggable output serializers.

**Core Principle**: Domain-agnostic extraction pipeline. Configure via prompts and schemas, not code changes.

---

## Technical Stack

**Backend**
- API: FastAPI + async processing
- LLM: GPT-5 via OpenAI Responses API with function calling
- PDF: PyMuPDF table detection + GPT-5 vision extraction
- Storage: SQLite + file system
- Output: Pluggable serializer architecture

**Frontend**
- Framework: React + Vite
- State: Zustand
- Testing: Vitest, Playwright for E2E

**Architecture**: Vision-First Extraction
- PyMuPDF crops tables from PDF pages
- GPT-5 vision analyzes cropped table images directly (no OCR)
- Structured output via function calling schemas

---

## OpenAI API Requirements

**MUST use Responses API, NOT chat.completions.**

Reference: `.claude/ai-docs/openAI_new/*.md` for API usage patterns.

### Correct Pattern
```python
response = await client.responses.create(
    model="gpt-5-mini",
    input=prompt,
    tools=[schema],
    tool_choice={"type": "function", "name": "extract_data"},
    reasoning={"effort": "low"},
    text={"verbosity": "low"}
)
```

### Schema Requirements
- MUST include: `"additionalProperties": false`
- MUST include: `"strict": true`
- All properties in `required` array

### Models
- `gpt-5` - Complex reasoning, broad knowledge
- `gpt-5-mini` - Cost-optimized (use for extraction)
- `gpt-5-nano` - High-throughput, simple tasks

---

## Code Standards

Enforced via `.claude/CODE_STANDARDS.md`.

- **PEP8**: snake_case, 100-char lines, proper imports
- **Functions**: 60 lines max, 5 parameters max, single responsibility
- **Type hints**: Required on all signatures
- **Error handling**: Specific exceptions (no bare `except:`)
- **Testing**: pytest for business logic

### Module Boundaries
```
src/backend/
├── core/       # Pipeline orchestration, models
├── llm/        # LLM client, extraction (GPT-5 Responses API)
├── pdf/        # Table detection, cropping
├── serializers/# Pluggable output generation
└── config/     # Settings, prompts, schemas
```

---

## Extending the Template

### Adding a New Output Format

1. Create serializer in `src/backend/serializers/`:
```python
from .base import FormatSerializer, register_serializer

@register_serializer("myformat")
class MyFormatSerializer(FormatSerializer):
    def serialize(self, data: dict) -> str:
        # Transform extracted data to output format
        return formatted_output
```

2. Add prompts in `src/backend/config/prompts/myformat/`
3. Add schemas in `src/backend/config/schemas/myformat/`

### Adding a New Document Type

1. Add document type detection in `src/backend/pdf/`
2. Create extraction prompts in `config/prompts/`
3. Define output schema in `config/schemas/`

---

## Key Files Reference

### Backend Critical Paths
- `src/backend/core/pipeline.py` - Pipeline orchestration
- `src/backend/llm/client.py` - GPT-5 Responses API client
- `src/backend/llm/async_extractor.py` - Parallel extraction
- `src/backend/llm/multipass_extractor.py` - Multi-pass extraction
- `src/backend/config/prompts/*.yaml` - Extraction prompts
- `src/backend/config/schemas/*.yaml` - Function calling schemas

### Serializers
- `src/backend/serializers/base.py` - Base class and registry

### Configuration
- `CLAUDE.md` - This file (project context)
- `.claude/CODE_STANDARDS.md` - Quality rules (local)
- `.claude/ai-docs/` - API reference docs (local)

---

## Style Guidelines

- Direct, clear, concise
- Tables over prose for structured data
- Line numbers for code references (file.py:123)
