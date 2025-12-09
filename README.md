# Document Processing Pipeline

Batch document processing framework that extracts structured data from PDF tables using GPT-5 vision. Sends cropped table images directly to the LLM, eliminating OCR errors. Multi-pass architecture separates classification, extraction, and normalization. Domain-agnostic by design: extraction schemas are external YAML, prompts are configurable per domain, and output formats are pluggable modules. Swap extraction strategies or add new serializers without touching core pipeline code.

## How It Works

1. Upload a PDF
2. System detects tables and crops them as images
3. GPT-5 vision analyzes each table image directly
4. Structured data extracted via function calling schemas
5. Output serialized to your chosen format

## Requirements

- Python 3.10+
- OpenAI API key with GPT-5 access
- Node.js 18+ (for web interface)

## Setup

```bash
# Clone and create virtual environment
git clone <repository>
cd <project-directory>
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Run
python run_api.py
```

Web interface (optional):
```bash
cd src/web/frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Configuration

Set these environment variables in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `EXTRACTION_SCHEMA` | No | Schema name for extraction (default: "extraction") |
| `PROMPT_DIRECTORY` | No | Prompt directory for your domain (default: "default") |
| `DEFAULT_OUTPUT_FORMAT` | No | Output format (default: "json") |

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all options.

## Project Structure

```
src/
├── backend/
│   ├── config/         # Settings, prompts, schemas
│   ├── llm/            # GPT-5 integration
│   ├── pdf/            # PDF processing
│   └── serializers/    # Output formats
└── web/
    ├── routes/         # API endpoints
    ├── jobs/           # Job queue
    └── frontend/       # React UI
```

## Adapting for Your Domain

1. **Create a schema** in `src/backend/config/schemas/`
   - Define the structure of data you want to extract
   - Use OpenAI function calling format

2. **Create prompts** in `src/backend/config/prompts/{your-domain}/`
   - Write instructions for the LLM

3. **Add a serializer** (optional) in `src/backend/serializers/`
   - Convert extracted data to your output format

4. **Set environment variables**
   ```
   EXTRACTION_SCHEMA=your_schema
   PROMPT_DIRECTORY=your-domain
   ```

## API

See [docs/API.md](docs/API.md) for endpoint documentation.

## Testing

```bash
pytest tests/
```

## License

MIT
