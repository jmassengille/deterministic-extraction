# API Reference

Base URL: `http://localhost:8000/api`

## Endpoints

### Health Check

```
GET /health
```

Returns server status.

```json
{
  "status": "healthy",
  "service": "Document Processing API",
  "version": "1.0.0",
  "worker_stats": {}
}
```

---

### Upload Document

```
POST /upload
```

Upload a PDF for processing.

**Form data:**
- `file` (required): PDF file
- `output_formats` (optional): Comma-separated formats, e.g., `json,csv`
- `metadata` (optional): JSON string with additional data

**Response (200):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "file_size": 12345,
  "output_formats": ["json"],
  "message": "File uploaded successfully. Job 550e8400... created."
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@document.pdf" \
  -F "output_formats=json"
```

---

### List Jobs

```
GET /jobs
```

**Query parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 20, max: 100)
- `status` (string): Filter by status

**Response:**
```json
{
  "jobs": [...],
  "total": 42,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

---

### Get Job

```
GET /jobs/{job_id}
```

Returns job details including status, progress, and output paths.

---

### Delete Job

```
DELETE /jobs/{job_id}
```

Cancels a running job or deletes a completed job. Returns 204 on success.

---

### Get Available Formats

```
GET /jobs/{job_id}/formats
```

Returns available download formats for a completed job.

**Response:**
```json
{
  "formats": [
    {
      "format": "json",
      "available": true,
      "path": "/path/to/output.json",
      "files": []
    }
  ]
}
```

The `files` array contains entries for multi-file formats.

---

### Download Output

```
GET /jobs/{job_id}/download
```

**Query parameters:**
- `format` (string): Output format (default: "json")
- `key` (string): For multi-file formats, the specific file key

Returns the output file.

---

### Progress Stream

```
GET /jobs/{job_id}/progress
```

Server-Sent Events stream for real-time progress updates.

**Event format:**
```json
{
  "job_id": "...",
  "progress": 75,
  "stage": "processing_data",
  "message": "Processing table 3 of 5",
  "timestamp": "2025-12-09T10:30:00Z",
  "details": {}
}
```

**Usage:**
```javascript
const eventSource = new EventSource(`/api/jobs/${jobId}/progress`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress}%`);
};
```

---

## Storage Endpoints

### Get Storage Stats

```
GET /storage/stats
```

Returns storage usage statistics.

```json
{
  "total_space": 1000000000,
  "used_space": 500000000,
  "available_space": 500000000,
  "pdf_count": 10,
  "pdf_size": 100000000,
  "msf_count": 10,
  "msf_size": 50000000,
  "temp_files_count": 5,
  "temp_files_size": 10000000
}
```

---

### Cleanup Storage

```
POST /storage/cleanup
```

**Query parameters:**
- `delete_completed_pdfs` (bool): Delete PDFs from completed jobs (default: true)
- `delete_old_msfs` (bool): Delete old output files (default: false)
- `msf_retention_days` (int): Days to retain outputs (default: 7)
- `clear_temp` (bool): Clear temporary files (default: true)

**Response:**
```json
{
  "deleted_pdfs": 5,
  "deleted_msfs": 3,
  "deleted_temp": 10,
  "space_freed": 50000000,
  "message": "Cleanup completed"
}
```

---

### Bulk Delete Jobs

```
DELETE /storage/jobs/bulk
```

**Request body:**
```json
{
  "job_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:**
```json
{
  "deleted": 3,
  "failed": [],
  "space_freed": 30000000,
  "message": "Bulk delete completed"
}
```

---

## Job Stages

Jobs progress through these stages:

| Stage | Description |
|-------|-------------|
| `queued` | Waiting to start |
| `loading_document` | Reading PDF |
| `analyzing_structure` | Finding tables |
| `extracting_regions` | Cropping table images |
| `processing_data` | LLM extraction |
| `generating_output` | Creating output files |
| `finalizing` | Cleanup |

---

## Job Statuses

| Status | Description |
|--------|-------------|
| `pending` | In queue |
| `processing` | Currently running |
| `completed` | Finished successfully |
| `failed` | Error occurred |
| `cancelled` | Stopped by user |

---

## Error Responses

All errors return:
```json
{
  "detail": "Error message"
}
```

| Code | Meaning |
|------|---------|
| 400 | Bad request |
| 404 | Not found |
| 409 | Conflict (e.g., job state error) |
| 500 | Server error |
