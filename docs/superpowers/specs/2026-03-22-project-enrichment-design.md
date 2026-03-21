# Project Enrichment: Auto-Fetch Brand Info from Website

**Date:** 2026-03-22
**Status:** Draft

## Problem

Creating a project only asks for a name. Users must manually fill in description, brand voice, offering, and other brand details. Since projects already have a `url` field and a `metadata_` JSON field, we can auto-populate brand info by scraping the project's website.

## Solution

When a user creates a project with a website URL, automatically fetch the site and use Claude Haiku to extract structured brand information. Store it in the project's `metadata_` JSON field.

## Backend

### New endpoint: `POST /api/projects/{project_id}/enrich`

1. Fetch the website HTML using httpx (10s timeout)
2. Strip HTML to text content using BeautifulSoup, truncate to ~4000 chars
3. Send to Claude Haiku with a structured extraction prompt
4. Store results in `metadata_["brand"]`
5. Update `description` if currently empty
6. Update `color` if a primary brand color is extracted
7. Set `metadata_["enrichment_status"]` to track progress
8. Broadcast update via WebSocket (`project.updated`)

### Auto-trigger on create

In the existing `POST /api/projects` endpoint, after creating the project:
- If `url` is provided, add a FastAPI `BackgroundTasks` call to run enrichment
- Set `metadata_["enrichment_status"] = "pending"` on creation

### Haiku prompt

Ask Haiku to return JSON with:
- `tagline` — the site's main tagline or value proposition
- `offering` — what the product/service does (2-3 sentences)
- `brand_voice` — description of the writing tone/style
- `tone_keywords` — list of 3-5 adjectives describing the tone
- `brand_colors` — list of hex colors found on the site (primary first)

### Error handling

- If the URL is unreachable: set `enrichment_status: "failed"`, log warning
- If Haiku can't extract useful info: set `enrichment_status: "partial"`, store what's available
- If no LLM API key configured: skip enrichment silently

### Data shape in `metadata_`

```json
{
  "brand": {
    "tagline": "Design faster with AI",
    "offering": "AI-powered design tool that generates production-ready UI components from natural language descriptions.",
    "brand_voice": "Professional yet approachable, technically confident, focused on empowering creators.",
    "tone_keywords": ["professional", "friendly", "empowering"],
    "brand_colors": ["#1a73e8", "#ffffff", "#202124"]
  },
  "enrichment_status": "completed"
}
```

## Dashboard

### Replace inline input with a dialog

Current: clicking "New Project" shows an inline text input for name only.

New: clicking "New Project" opens a modal dialog with:
- **Project name** — text input (required)
- **Website URL** — text input (optional), placeholder "https://..."
- **Create** button

On submit:
1. Call `POST /api/projects` with `{ name, url }`
2. Close dialog
3. Project appears in list immediately
4. If URL was provided, enrichment runs in background
5. Project card shows a subtle loading state on the brand section while `enrichment_status === "pending"`
6. WebSocket update triggers re-render with enriched data

### Project card updates

Show brand info from `metadata_.brand` on the project card:
- Tagline displayed under the project name
- Offering shown in the description area (if description is empty)
- Brand voice and tone keywords visible in an expandable section or tooltip

## API client

Add to `dashboard/app/lib/api.ts`:
- `projects.enrich(id)` — calls `POST /api/projects/{project_id}/enrich`

## Files to modify

- `backend/app/api/projects.py` — add enrich endpoint, modify create to trigger background enrichment
- `dashboard/app/projects/page.tsx` — replace inline input with dialog, show brand metadata on cards
- `dashboard/app/lib/api.ts` — add enrich method

## Dependencies

- `httpx` — already in backend dependencies
- `beautifulsoup4` — may need to add to requirements
- Claude Haiku API — uses existing LLM infrastructure from `backend/app/config.py`
