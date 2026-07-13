# API reference

## Conventions

- Base path: `/api/v1`
- Request and response encoding: JSON, except multipart resume upload and binary exports
- Resource identifiers: UUID strings
- Timestamps: ISO 8601 UTC timestamps
- Authentication: bearer API key on every resume, job, and match route
- Error media type: `application/problem+json`
- Request correlation: send an optional UUID in `X-Request-ID`; every normal application response returns the accepted or generated UUID in the same header

The generated OpenAPI document is available at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc` when `APP_ENV` is not `production`. They are disabled in production by design.

## Authentication

Configure one or more comma-separated keys:

```dotenv
APP_API_KEYS=a-long-random-key,another-key-during-rotation
```

Send one key as a bearer credential:

```http
Authorization: Bearer a-long-random-key
```

When `APP_API_KEYS` is empty, protected routes allow unauthenticated requests. This is intended only for local development; production configuration rejects an empty key list. Keys are application-wide in this single-tenant MVP—there is no per-user identity or resource ownership.

An absent or invalid configured credential returns `401` with `WWW-Authenticate: Bearer`.

## Endpoint summary

| Method | Path | Auth | Success | Description |
|---|---|---|---:|---|
| `GET` | `/health/live` | Public | 200 | Process liveness |
| `GET` | `/health/ready` | Public | 200 or 503 | Database readiness and configured AI adapter |
| `POST` | `/resumes` | Bearer | 201 | Upload and extract a resume |
| `GET` | `/resumes/{resume_id}` | Bearer | 200 | Retrieve structured resume data |
| `DELETE` | `/resumes/{resume_id}` | Bearer | 200 | Delete resume metadata and original file |
| `POST` | `/jobs` | Bearer | 201 | Extract and store a job description |
| `GET` | `/jobs/{job_id}` | Bearer | 200 | Retrieve structured job data |
| `POST` | `/matches` | Bearer | 201 | Compute and store a deterministic match |
| `GET` | `/matches/{match_id}` | Bearer | 200 | Retrieve a match analysis |
| `POST` | `/matches/{match_id}/optimize` | Bearer | 200 | Generate and validate an optimized draft |
| `GET` | `/matches/{match_id}/exports/{format}` | Bearer | 200 | Download `json`, `docx`, or `pdf` |

`POST /resumes`, `POST /jobs`, `POST /matches`, and `POST /matches/{id}/optimize` use the built-in rate limiter. A rejected request returns `429` and `Retry-After`. The limiter is in memory and per worker; production deployments need a shared edge control.

## Complete example workflow

The examples use shell variables and illustrative UUIDs. Replace them with IDs returned by your instance.

```bash
export BASE_URL=http://localhost:8000/api/v1
export API_KEY=replace-with-your-configured-key
```

### 1. Check readiness

```bash
curl --fail-with-body "$BASE_URL/health/ready"
```

```json
{
  "status": "ok",
  "version": "0.1.0",
  "checks": {
    "database": "ok",
    "ai_provider": "local"
  }
}
```

`ai_provider` reports configuration, not a live external-provider probe.

### 2. Upload a resume

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Request-ID: 51f09d15-7e7c-4730-8247-8ef40577f1e8" \
  -F "file=@/path/to/resume.pdf;type=application/pdf" \
  "$BASE_URL/resumes"
```

Representative `201 Created` response:

```json
{
  "id": "78b5d59f-115f-42ee-9787-c11592e3400d",
  "filename": "resume.pdf",
  "content_type": "application/pdf",
  "sha256": "ec86f73b4613e8c88c74f768fe2b65e9d689e2e0d1dc655480bb41ef2c02347f",
  "profile": {
    "name": "Alex Rivera",
    "headline": "Senior Software Engineer",
    "summary": "Engineer building reliable Python services.",
    "email": "alex@example.com",
    "phone": "+1 555 010 2000",
    "location": "New York, NY",
    "skills": [
      {"name": "AWS", "normalized_name": "aws"},
      {"name": "Docker", "normalized_name": "docker"},
      {"name": "FastAPI", "normalized_name": "fastapi"},
      {"name": "Python", "normalized_name": "python"}
    ],
    "experiences": [
      {
        "title": "Senior Software Engineer",
        "company": "Example Labs",
        "start_date": "2022",
        "end_date": "Present",
        "location": "New York, NY",
        "bullets": ["Built reliable Python APIs and deployed them with Docker."],
        "skills": ["Python", "Docker"]
      }
    ],
    "education": [
      {
        "institution": "Example University",
        "degree": "Bachelor of Science",
        "field": "Computer Science",
        "graduation_year": 2021,
        "level": "bachelor"
      }
    ],
    "certifications": [],
    "total_years_experience": 4.0,
    "keywords": ["services", "reliability", "apis"]
  },
  "created_at": "2026-07-13T14:00:00Z",
  "warnings": []
}
```

The API response intentionally omits `raw_text`, although the extracted raw text remains in persistence and may be present in JSON exports. An exact duplicate upload returns the existing resource with status `201` and this warning:

```json
{
  "warnings": [
    "An identical resume was already uploaded; returning the existing resource."
  ]
}
```

The warning snippet above shows only the changed field; the actual response remains a complete `ResumeResponse`.

### 3. Create a job description

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Senior AI Engineer at Example Corp\n\nRequired skills: Python, FastAPI, Docker, PostgreSQL, and 5+ years of experience.\nPreferred: AWS and Kubernetes.\nBachelor degree required.\nBuild reliable AI APIs.\nLead and mentor engineers."
  }' \
  "$BASE_URL/jobs"
```

Representative `201 Created` response:

```json
{
  "id": "d83fc16f-c5c1-4df2-9d5e-31cb043e13c8",
  "profile": {
    "title": "Senior AI Engineer",
    "company": "Example Corp",
    "summary": "Build reliable AI APIs and mentor engineers.",
    "required_skills": [
      {"name": "Docker", "normalized_name": "docker"},
      {"name": "FastAPI", "normalized_name": "fastapi"},
      {"name": "PostgreSQL", "normalized_name": "postgresql"},
      {"name": "Python", "normalized_name": "python"}
    ],
    "preferred_skills": [
      {"name": "AWS", "normalized_name": "aws"},
      {"name": "Kubernetes", "normalized_name": "kubernetes"}
    ],
    "responsibilities": ["Build reliable AI APIs", "Mentor engineers"],
    "education_level": "bachelor",
    "minimum_years_experience": 5.0,
    "keywords": ["reliable", "apis", "mentor", "engineers"]
  },
  "created_at": "2026-07-13T14:01:00Z"
}
```

The request must contain 100–200,000 characters by schema and must also remain at or below `APP_MAX_JOB_DESCRIPTION_CHARS` (50,000 by default).

### 4. Create a match

```bash
export RESUME_ID=78b5d59f-115f-42ee-9787-c11592e3400d
export JOB_ID=d83fc16f-c5c1-4df2-9d5e-31cb043e13c8

curl --fail-with-body \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"resume_id\":\"$RESUME_ID\",\"job_id\":\"$JOB_ID\"}" \
  "$BASE_URL/matches"
```

Representative `201 Created` response:

```json
{
  "id": "80dfbe8d-721a-42d6-a922-331cc683e866",
  "resume_id": "78b5d59f-115f-42ee-9787-c11592e3400d",
  "job_id": "d83fc16f-c5c1-4df2-9d5e-31cb043e13c8",
  "result": {
    "overall_score": 70.2,
    "dimensions": [
      {
        "name": "skills",
        "weight": 0.45,
        "raw_score": 70.0,
        "weighted_score": 31.5,
        "matched": ["Docker", "FastAPI", "Python", "AWS"],
        "missing": ["PostgreSQL", "Kubernetes"],
        "explanation": "Matched 3/4 required and 1/2 preferred skills."
      },
      {
        "name": "experience",
        "weight": 0.25,
        "raw_score": 80.0,
        "weighted_score": 20.0,
        "matched": ["4 years"],
        "missing": ["5 years required"],
        "explanation": "Resume evidence indicates 4 years against a 5-year minimum."
      },
      {
        "name": "keywords",
        "weight": 0.15,
        "raw_score": 50.0,
        "weighted_score": 7.5,
        "matched": ["apis", "reliable"],
        "missing": ["engineers", "mentor"],
        "explanation": "Matched 2/4 normalized job keywords."
      },
      {
        "name": "education",
        "weight": 0.1,
        "raw_score": 100.0,
        "weighted_score": 10.0,
        "matched": ["bachelor"],
        "missing": [],
        "explanation": "Highest extracted level (bachelor) meets the bachelor requirement."
      },
      {
        "name": "responsibilities",
        "weight": 0.05,
        "raw_score": 25.0,
        "weighted_score": 1.25,
        "matched": ["apis"],
        "missing": [],
        "explanation": "Token overlap between documented achievements and job responsibilities; this is a small supporting signal, not an LLM-assigned score."
      }
    ],
    "matched_skills": ["AWS", "Docker", "FastAPI", "Python"],
    "missing_required_skills": ["PostgreSQL"],
    "missing_preferred_skills": ["Kubernetes"],
    "matched_keywords": ["apis", "reliable"],
    "missing_keywords": ["engineers", "mentor"],
    "recommendations": [
      {
        "category": "skills",
        "priority": "high",
        "title": "Address required-skill evidence",
        "guidance": "For each missing required skill, add a concrete achievement only if the experience is true. Otherwise, treat it as a learning gap and never claim it.",
        "evidence": ["PostgreSQL"]
      },
      {
        "category": "experience",
        "priority": "high",
        "title": "Clarify relevant experience depth",
        "guidance": "The job asks for 5 years while the resume supports 4. Make dates, scope, and directly relevant achievements explicit; do not inflate tenure.",
        "evidence": []
      },
      {
        "category": "skills",
        "priority": "medium",
        "title": "Surface preferred qualifications",
        "guidance": "Add these only where the resume can support them with real evidence.",
        "evidence": ["Kubernetes"]
      },
      {
        "category": "keywords",
        "priority": "low",
        "title": "Use the employer's terminology naturally",
        "guidance": "Where accurate, align wording with the job description inside achievement bullets. Avoid keyword stuffing or hidden text.",
        "evidence": ["engineers", "mentor"]
      }
    ],
    "explanation": "The 70.2% score is the weighted result of five deterministic dimensions. The strongest dimension is education (100.0%), while responsibilities (25.0%) has the largest improvement opportunity.",
    "score_version": "1.0.0"
  },
  "optimized_resume": null,
  "created_at": "2026-07-13T14:02:00Z",
  "updated_at": "2026-07-13T14:02:00Z"
}
```

This example is illustrative but follows the exact response schema. Actual extraction and calculations depend on submitted content and the selected intelligence adapter.

### 5. Optimize the resume

```bash
export MATCH_ID=80dfbe8d-721a-42d6-a922-331cc683e866

curl --fail-with-body -X POST \
  -H "Authorization: Bearer $API_KEY" \
  "$BASE_URL/matches/$MATCH_ID/optimize"
```

The `200 OK` response is the same `MatchResponse` schema. `optimized_resume` changes from `null` to an object containing identity fields, skills, experiences, education, certifications, a `changes` audit list, and warnings:

```json
{
  "name": "Alex Rivera",
  "headline": "Senior Software Engineer",
  "summary": "Engineer building reliable Python services. Relevant strengths include AWS, Docker, FastAPI, Python.",
  "email": "alex@example.com",
  "phone": "+1 555 010 2000",
  "location": "New York, NY",
  "skills": [
    {"name": "AWS", "normalized_name": "aws"},
    {"name": "Docker", "normalized_name": "docker"},
    {"name": "FastAPI", "normalized_name": "fastapi"},
    {"name": "Python", "normalized_name": "python"}
  ],
  "experiences": [
    {
      "title": "Senior Software Engineer",
      "company": "Example Labs",
      "start_date": "2022",
      "end_date": "Present",
      "location": "New York, NY",
      "bullets": ["Built reliable Python APIs and deployed them with Docker."],
      "skills": ["Python", "Docker"]
    }
  ],
  "education": [
    {
      "institution": "Example University",
      "degree": "Bachelor of Science",
      "field": "Computer Science",
      "graduation_year": 2021,
      "level": "bachelor"
    }
  ],
  "certifications": [],
  "changes": [
    {
      "section": "summary",
      "before": "Engineer building reliable Python services.",
      "after": "Engineer building reliable Python services. Relevant strengths include AWS, Docker, FastAPI, Python.",
      "reason": "Surfaces job-relevant skills already present in the source resume.",
      "source_evidence": ["Engineer building reliable Python services."]
    }
  ],
  "warnings": [
    "Local mode only reorders existing evidence and adds a summary from verified skills.",
    "Review every statement before submitting the resume."
  ]
}
```

The snippet above is the complete nested `optimized_resume` value, not the complete enclosing `MatchResponse`. OpenAI mode may rewrite more content than local mode. In both modes, a fact guard runs before persistence. It preserves name/contact fields, role dates/location, and education metadata; rejects added skills, certifications, roles, and education; and requires non-empty source-present evidence for every recorded change. Changed headline/summary text and non-reordering experience bullet/skill content also require a corresponding evidence record. A `422` means it detected unsupported content; passing the guard is not a semantic guarantee that every evidence-grounded rewrite is true.

### 6. Export results

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $API_KEY" \
  -o analysis.json \
  "$BASE_URL/matches/$MATCH_ID/exports/json"

curl --fail-with-body \
  -H "Authorization: Bearer $API_KEY" \
  -o optimized-resume.docx \
  "$BASE_URL/matches/$MATCH_ID/exports/docx"

curl --fail-with-body \
  -H "Authorization: Bearer $API_KEY" \
  -o optimized-resume.pdf \
  "$BASE_URL/matches/$MATCH_ID/exports/pdf"
```

| Format | Media type | Contents |
|---|---|---|
| `json` | `application/json` | Schema version, generation time, selected resume, target job, complete match result, and optimization flag. The target job includes raw text. The selected resume includes raw text before optimization; an `OptimizedResume` does not have that field. |
| `docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Optimized resume when available, otherwise the original structured resume. |
| `pdf` | `application/pdf` | Optimized resume when available, otherwise the original structured resume. |

Responses include `Content-Disposition: attachment` with a server-generated filename. JSON exports are substantially more sensitive than ordinary API responses because dataclass serialization includes raw job text and can include raw resume text.

### 7. Delete the source resume

```bash
curl --fail-with-body -X DELETE \
  -H "Authorization: Bearer $API_KEY" \
  "$BASE_URL/resumes/$RESUME_ID"
```

```json
{
  "deleted": true
}
```

The service deletes the database resume row and the UUID-addressed original file. Match rows reference resumes with `ON DELETE CASCADE` at the database schema level. Deletion is not a substitute for backup-expiration or storage-volume lifecycle policy.

## Resource details

### `POST /resumes`

- Body: multipart form with exactly one required `file` field.
- Extensions: `.pdf` and `.docx` only.
- PDF: validates magic bytes, rejects password protection, supports at most 100 pages, requires selectable text, and does not perform OCR.
- DOCX: validates ZIP/Word parts, rejects macro parts, limits total uncompressed size to 50 MiB, and rejects suspicious large-entry compression ratios.
- Extracted text: capped at 500,000 characters with a response warning when truncated.
- Duplicate behavior: SHA-256 duplicate detection returns the existing resource.
- Common errors: `400`, `401`, `413`, `415`, `429`, `502`, `503`.

### `GET /resumes/{resume_id}`

Returns the same `ResumeResponse` schema without upload-time parser warnings. Raw source text is not returned by this endpoint.

### `DELETE /resumes/{resume_id}`

Deletes metadata and the original file. Returns `404` if the resource does not exist. There is no undelete operation.

### `POST /jobs`

```json
{
  "job_description": "At least 100 characters of job-description text"
}
```

The Pydantic schema permits at most 200,000 characters, while the configured application limit may be lower. Common errors: `401`, `413`, `422`, `429`, `502`, `503`.

### `POST /matches`

```json
{
  "resume_id": "78b5d59f-115f-42ee-9787-c11592e3400d",
  "job_id": "d83fc16f-c5c1-4df2-9d5e-31cb043e13c8"
}
```

Returns `404` when either source resource is missing. Match creation is synchronous and deterministic after profiles have been extracted. Repeating the request creates another match resource; no idempotency key is implemented.

### `POST /matches/{match_id}/optimize`

Has no request body. The current implementation regenerates and overwrites the nested optimized draft on each successful call. In OpenAI mode, the operation is synchronous and subject to configured provider timeout/retry behavior.

### `GET /matches/{match_id}/exports/{format_name}`

`format_name` is validated at routing time and must be `json`, `docx`, or `pdf`. There is no HTML export.

## Shared schema notes

| Type | Values or constraints |
|---|---|
| `EducationLevel` | `none`, `high_school`, `associate`, `bachelor`, `master`, `doctorate` |
| Recommendation priority | `high`, `medium`, `low` |
| `SkillResponse` | Display `name` plus canonical `normalized_name` |
| Score dimension | Name, weight, raw score, weighted score, matched/missing evidence, explanation |
| Optimization change | Section, before/after values, reason, and source evidence |

All API Pydantic models reject unknown fields. This prevents silently accepting misspelled request properties.

## Error format

Handled errors use a Problem Details-style document:

```json
{
  "type": "urn:resume-matcher:error:request_validation_error",
  "title": "Request validation failed",
  "status": 422,
  "detail": "One or more request fields are invalid",
  "instance": "/api/v1/matches",
  "code": "request_validation_error",
  "request_id": "51f09d15-7e7c-4730-8247-8ef40577f1e8",
  "errors": [
    {
      "location": ["body", "resume_id"],
      "message": "Input should be a valid UUID",
      "type": "uuid_parsing"
    }
  ]
}
```

The request-size middleware emits the same core Problem Details fields for an invalid `Content-Length` or an actual body over the cap, even though it rejects the request before route handling. A degraded readiness probe is the one operational exception: it returns the `HealthResponse` schema with status `503`.

| Status | Typical meaning |
|---:|---|
| 400 | Invalid `Content-Length`; empty, corrupted, password-protected, non-text, or structurally invalid document |
| 401 | Missing or invalid configured API key |
| 404 | Resume, job, or match UUID not found |
| 413 | Request, upload, archive expansion, or job text exceeds a safety limit |
| 415 | Unsupported resume extension |
| 422 | Request schema validation or factual-integrity failure |
| 429 | In-process request rate limit reached |
| 500 | Unhandled application failure |
| 502 | AI provider rejected a request or returned an unusable result |
| 503 | Database readiness failure or temporarily unavailable AI provider |

Provider-unavailable responses include `Retry-After: 5`; rate-limit responses include a calculated `Retry-After` value.

## API lifecycle limitations

- There are no list endpoints, pagination, job deletion, match deletion, batch operations, asynchronous status endpoints, or idempotency-key support.
- Resource knowledge is by UUID; a valid application API key is still authorized for every UUID in this single-tenant release.
- Processing may take as long as parsing plus OpenAI timeout/retries because there is no background queue.
- Ordinary API response models omit raw text, but persistence retains it. JSON exports always include raw job text and include raw resume text when the selected resume is the original profile rather than an optimized draft.
- `APP_DATA_RETENTION_DAYS` is not enforced by a cleanup process.
- Version `v1` is the transport contract. Numeric scoring is independently versioned through `score_version`.
