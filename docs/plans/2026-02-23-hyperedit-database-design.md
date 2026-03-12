# HyperEdit AI Database Schema Design

**Date:** 2026-02-23
**Status:** Implementation
**Supabase Project:** bbkdzfxdbeclyxoaaadb (shared with FOFAL ERP)
**Namespace:** All tables prefixed `he_` to isolate from FOFAL's 245+ tables

## Goal

Replace JSON file persistence (`logs/scheduler_state.json`) with a proper PostgreSQL
database for job tracking, pipeline execution, asset management, QA results, and
analytics — enabling the autonomous video editing pipeline to be production-grade.

## Architecture

- **8 tables** in `public` schema with `he_` prefix
- **RLS enabled** on all tables (authenticated access)
- **JSONB** for flexible skill configs and results
- **Enums** for type-safe status tracking
- **Triggers** for automatic `updated_at` timestamps
- **Indexes** on frequently queried columns (status, job_id, created_at)

## Tables

### 1. `he_video_jobs` — Core job entity
Tracks each video editing job from queue to completion.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | gen_random_uuid() |
| title | text NOT NULL | Job name / video title |
| status | he_job_status enum | queued → processing → completed / failed / cancelled |
| input_path | text NOT NULL | Source video file path |
| output_path | text | Final output file path |
| pipeline | text[] | Ordered skill names: `{dead-air, audio, captions}` |
| config | jsonb DEFAULT '{}' | Job-level overrides |
| priority | int DEFAULT 0 | Higher = more urgent |
| retry_count | int DEFAULT 0 | Current retry attempt |
| max_retries | int DEFAULT 3 | Max allowed retries |
| error_message | text | Last error if failed |
| started_at | timestamptz | Processing start |
| completed_at | timestamptz | Processing end |
| created_at | timestamptz DEFAULT now() | |
| updated_at | timestamptz DEFAULT now() | Auto-updated via trigger |

### 2. `he_pipeline_steps` — Skill execution tracking
Each row = one skill execution within a job pipeline.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| job_id | uuid FK → he_video_jobs | CASCADE delete |
| skill_name | text NOT NULL | e.g., 'dead-air', 'captions' |
| step_order | int NOT NULL | Execution sequence |
| status | he_step_status enum | pending → running → completed / failed / skipped |
| input_path | text | Input for this step |
| output_path | text | Output from this step |
| config | jsonb DEFAULT '{}' | Skill-specific params |
| result | jsonb | Skill return dict |
| duration_ms | int | Execution time |
| error_message | text | |
| started_at | timestamptz | |
| completed_at | timestamptz | |
| created_at | timestamptz DEFAULT now() | |

### 3. `he_video_metadata` — FFprobe metadata
Cached video metadata for any file (input or output).

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| job_id | uuid FK → he_video_jobs | nullable (standalone scans) |
| file_path | text NOT NULL | |
| duration | float8 | seconds |
| width | int | pixels |
| height | int | pixels |
| fps | float8 | |
| codec | text | e.g., 'h264' |
| bitrate | int | bits/s |
| file_size_bytes | bigint | |
| has_audio | boolean | |
| audio_codec | text | |
| audio_sample_rate | int | |
| raw_metadata | jsonb | Full ffprobe output |
| created_at | timestamptz DEFAULT now() | |

### 4. `he_pipeline_assets` — Generated assets
Tracks all generated files (thumbnails, GIFs, captions, etc.)

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| job_id | uuid FK → he_video_jobs | CASCADE |
| step_id | uuid FK → he_pipeline_steps | nullable |
| asset_type | he_asset_type enum | thumbnail, gif, caption_srt, etc. |
| file_path | text NOT NULL | |
| file_size_bytes | bigint | |
| mime_type | text | |
| metadata | jsonb DEFAULT '{}' | Asset-specific info |
| created_at | timestamptz DEFAULT now() | |

### 5. `he_brand_kits` — Brand identity configs
Stores brand configurations for consistent video branding.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| name | text NOT NULL UNIQUE | |
| is_default | boolean DEFAULT false | |
| colors | jsonb | {primary, secondary, accent, bg, text} |
| fonts | jsonb | {heading, body, accent} |
| logo_path | text | |
| watermark_path | text | |
| lower_third_template | jsonb | Animation config |
| intro_path | text | |
| outro_path | text | |
| audio_signature_path | text | |
| config | jsonb DEFAULT '{}' | Additional settings |
| created_at | timestamptz DEFAULT now() | |
| updated_at | timestamptz DEFAULT now() | |

### 6. `he_video_templates` — Reusable pipeline templates

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| name | text NOT NULL UNIQUE | |
| description | text | |
| pipeline | text[] | Ordered skill names |
| default_config | jsonb DEFAULT '{}' | Defaults per skill |
| is_system | boolean DEFAULT false | Built-in templates |
| usage_count | int DEFAULT 0 | |
| created_at | timestamptz DEFAULT now() | |
| updated_at | timestamptz DEFAULT now() | |

### 7. `he_qa_results` — Quality assurance checks

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| job_id | uuid FK → he_video_jobs | CASCADE |
| step_id | uuid FK → he_pipeline_steps | nullable |
| check_name | text NOT NULL | e.g., 'duration', 'resolution' |
| passed | boolean NOT NULL | |
| severity | he_qa_severity enum | error, warning, info |
| message | text | |
| expected_value | text | |
| actual_value | text | |
| created_at | timestamptz DEFAULT now() | |

### 8. `he_notification_logs` — Notification history

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| job_id | uuid FK → he_video_jobs | nullable |
| channel | he_notification_channel enum | telegram, webhook, email |
| status | he_notification_status enum | sent, failed, pending |
| message | text NOT NULL | |
| response | jsonb | API response payload |
| error_message | text | |
| created_at | timestamptz DEFAULT now() | |

## Enums

- `he_job_status`: queued, processing, completed, failed, cancelled
- `he_step_status`: pending, running, completed, failed, skipped
- `he_asset_type`: thumbnail, gif, caption_srt, caption_vtt, chapter_json, chapter_youtube, transcript, audio, short_form, brand_overlay, export
- `he_qa_severity`: error, warning, info
- `he_notification_channel`: telegram, webhook, email
- `he_notification_status`: sent, failed, pending

## Indexes

- `he_video_jobs(status)` — Job queue queries
- `he_video_jobs(created_at DESC)` — Recent jobs
- `he_pipeline_steps(job_id, step_order)` — Pipeline execution order
- `he_video_metadata(job_id)` — Metadata lookup
- `he_video_metadata(file_path)` — Cache lookup
- `he_pipeline_assets(job_id)` — Asset retrieval
- `he_qa_results(job_id)` — QA lookup
- `he_notification_logs(job_id)` — Notification history

## RLS Policy

All tables: `ENABLE ROW LEVEL SECURITY` with authenticated read/write policies.
Since HyperEdit is a single-user/team tool, RLS allows all authenticated users.

## Triggers

- `updated_at` auto-trigger on: he_video_jobs, he_brand_kits, he_video_templates
- `set_default_brand_kit` — ensures only one brand kit is default

## Seed Data

- 3 system templates: "Quick Edit" (dead-air + audio + captions), "Full Production" (all 18 skills), "Social Media" (short-form + gif + thumbnail + export)
