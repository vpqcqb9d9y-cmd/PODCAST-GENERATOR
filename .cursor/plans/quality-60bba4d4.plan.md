<!-- 60bba4d4-d352-4981-a30a-68dc21fe3810 d4bc1004-4bc3-472a-a983-4b38248741d3 -->
# Enhanced Visual Metadata Generation System

## Overview

Enhance the metadata generation system to create professional-grade visual metadata matching the user's example format, including detailed image prompts (10 images), video metadata, background context, and general notes.

## Current State

- Basic metadata generated in `src/metadata/chat.py` via `bootstrap_from_transcript()`
- Simple system prompt in `src/utils/config.py` (`metadata_system_prompt`)
- Metadata stored in `metadata.json` with basic fields: topic, summary, key_concepts, labs, etc.
- Visual generators use simple prompts without detailed metadata

## Implementation Plan

### 1. Enhance Metadata Schema (`src/metadata/chat.py`)

**Add new method `generate_visual_metadata()`:**

- Takes transcript and existing metadata as input
- Generates detailed visual metadata matching user's format:
  - `background`: Contextual background about the content (רקע מזרחי)
  - `images`: Array of 10 image objects, each with:
    - `prompt`: Detailed English prompt for image generation
    - `style`: Photography/art style (e.g., "Documentary Photography, Natural Lighting, 35mm")
    - `mood`: Emotional tone (e.g., "התמדה, בדידות יצירתית, נחישות")
    - `color_palette`: Color scheme (e.g., "חום חם, בז', אבן ירושלמית")
    - `background_context`: Symbolic/contextual meaning
  - `video`: Video metadata with:
    - `title`: Video title
    - `duration`: Duration in seconds
    - `prompt`: Detailed video generation prompt
    - `style`: Video style description
    - `scene_structure`: Array of scene timestamps and descriptions
    - `mood`: Overall mood
    - `color_palette`: Color scheme
    - `music`: Music reference
    - `background_context`: Contextual meaning
  - `general_notes`: Aesthetic and message notes

**Update `_default_metadata()`:**

- Keep basic fields in `metadata.json`
- Visual metadata will be stored separately

### 2. Enhanced System Prompt (`src/utils/config.py`)

**Add new environment variable `VISUAL_METADATA_SYSTEM_PROMPT`:**

- Detailed prompt instructing AI to generate professional visual metadata
- Includes examples and structure requirements
- Emphasizes Middle Eastern Israeli aesthetic when relevant
- Instructions for creating 10 sequential images that tell a story
- Video metadata with scene-by-scene breakdown

**Update `Settings` class:**

- Add `visual_metadata_system_prompt` field with default value

### 3. Visual Metadata Storage (`src/metadata/chat.py`)

**Add method `export_visual_metadata()`:**

- Returns visual metadata dict separate from basic metadata
- Called after `generate_visual_metadata()` completes

**Update `bootstrap_from_transcript()`:**

- Keep generating basic metadata automatically
- Visual metadata generation remains manual (via new method)

### 4. Integration with Pipeline (`src/pipeline/runner.py`)

**Update pipeline to:**

- Check for `visual_metadata.json` in run directory
- If exists, use detailed prompts from visual metadata
- Fall back to basic metadata if visual metadata not available
- Save `visual_metadata.json` alongside `metadata.json` in output directory

### 5. Visual Generator Integration (`src/visuals/google_ai_visuals.py`)

**Update `build_visuals_for_dialogue()`:**

- Check for `visual_metadata.json` in run_paths
- If available, use detailed prompts from `images` array
- Extract style, mood, color palette for enhanced prompt generation
- Fall back to current logic if visual metadata not available

**Enhance prompt generation:**

- Use detailed metadata fields to create richer prompts
- Include style, mood, and color palette in final prompts sent to Imagen/VEO

### 6. GUI Integration (`src/gui/app.py`)

**Add "Generate Visual Metadata" button:**

- In metadata panel or control panel
- Triggers `generate_visual_metadata()` on current transcript/metadata
- Shows progress indicator during generation
- Displays generated visual metadata in preview

**Add visual metadata preview:**

- Show image prompts, styles, moods in formatted display
- Allow editing before saving

### 7. CLI Support (`scripts/generate_podcast.py`)

**Add `--generate-visual-metadata` flag:**

- Triggers visual metadata generation before pipeline execution
- Saves `visual_metadata.json` in output directory

## Files to Modify

1. **`src/metadata/chat.py`**

   - Add `generate_visual_metadata()` method
   - Add `export_visual_metadata()` method
   - Update `_invoke_model()` to handle longer prompts (increase max_tokens)

2. **`src/utils/config.py`**

   - Add `visual_metadata_system_prompt` field to `Settings`
   - Add default prompt with detailed instructions

3. **`src/pipeline/runner.py`**

   - Load `visual_metadata.json` if exists
   - Pass visual metadata to visual generators

4. **`src/visuals/google_ai_visuals.py`**

   - Update `build_visuals_for_dialogue()` to use visual metadata
   - Enhance prompt generation with detailed metadata fields

5. **`src/gui/app.py`**

   - Add visual metadata generation button
   - Add visual metadata preview panel
   - Connect UI to `generate_visual_metadata()` method

6. **`scripts/generate_podcast.py`**

   - Add `--generate-visual-metadata` CLI flag

## Implementation Details

### Visual Metadata JSON Structure

```json
{
  "background": "רקע מזרחי...",
  "images": [
    {
      "index": 1,
      "title": "נער בדרכו הביתה מבית הספר",
      "prompt": "Israeli young boy...",
      "style": "Documentary Photography, Natural Lighting, 35mm",
      "mood": "התמדה, בדידות יצירתית, נחישות",
      "color_palette": "חום חם, בז', אבן ירושלמית, שמיים כחולים",
      "background_context": "שכונה ישראלית אותנטית..."
    },
    ...
  ],
  "video": {
    "title": "המדומיין - סיפור ויזואלי",
    "duration": 201,
    "prompt": "Short cinematic-documentary style clip...",
    "style": "Documentary-Cinematic, Natural Light...",
    "scene_structure": [
      {"start": "0:00", "end": "0:30", "description": "הליכה מבית הספר..."},
      ...
    ],
    "mood": "מעורר השראה, ריאליסטי, רגשי",
    "color_palette": "זהוב-חום של אבן ירושלמית...",
    "music": "המדומיין - פאר טסי",
    "background_context": "הסרטון מתעד את מהות השיר..."
  },
  "general_notes": {
    "aesthetics": "אסתטיקה מזרחית...",
    "messages": "מסרי השיר..."
  }
}
```

### System Prompt Template

The visual metadata system prompt will instruct the AI to:

- Analyze the transcript/content deeply
- Create a narrative arc across 10 images
- Match Middle Eastern Israeli aesthetic when relevant
- Include detailed technical specifications (style, mood, colors)
- Create video metadata with scene-by-scene breakdown
- Provide contextual meaning for each visual element

## Testing Strategy

1. Test with Hebrew song transcript (Peer Tassi example)
2. Verify visual metadata structure matches user's format
3. Test integration with visual generators
4. Verify fallback to basic metadata when visual metadata unavailable
5. Test GUI button and preview display