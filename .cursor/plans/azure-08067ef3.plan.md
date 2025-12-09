<!-- 08067ef3-9fc0-492e-be20-7f031be8af1a 30e13c47-75d2-4aa8-84a1-96f5a433001e -->
# Project & Performance Enhancements

## 1. Explorer actions & project loading

- In `src/gui/app.py`, add buttons to the “סייר תוצרים” card that allow the user to select a project directory to load (populate panels with its data) and delete a selected project (physically removing its folder after confirmation).

## 2. Onboarding wizard + README refresh

- Update the wizard copy to reflect the rebranded experience (M.B.S Studio, cost center button, explorer actions) and mirror those instructions inside the README for user onboarding.

## 3. Video reliability & responsiveness

- Revisit `src/pipeline/runner.py` and the video pipeline so slide-based fallback never crashes and generation time is trimmed where possible (e.g., skipping redundant renders, caching slide backgrounds). Profile any obvious bottlenecks and adjust logging to surface speed improvements.

### To-dos

- [x] Transcript fallback + bilingual UI
- [x] Split budget banner from analytics panel
- [x] Editable metadata + better project tree
- [x] Update onboarding wizard + README
- [x] Fix gallery status + PPT/network map
- [x] Add real-world pricing guidance
- [ ] Add visual analytics (cost chart, timeline improvements)
- [ ] Advanced outputs previews (gallery/PDF)
- [ ] Onboarding wizard + tooltips
- [ ] Scaffold src tree, deps, env config
- [ ] Build Azure OpenAI dialogue generator
- [ ] Implement Speech TTS + segment export
- [ ] Stitch audio, apply music/metadata
- [ ] Add orchestration CLI, logging, docs
- [ ] Scaffold src tree, deps, env config
- [ ] Build Azure OpenAI dialogue generator
- [ ] Implement Speech TTS + segment export
- [ ] Stitch audio, apply music/metadata
- [ ] Add orchestration CLI, logging, docs
- [ ] Add PyQt dependency, create gui module
- [ ] Implement PyQt GUI components
- [ ] Add pipeline runner worker logic
- [ ] Add GUI launch scripts and README docs
- [ ] Scaffold src tree, deps, env config
- [ ] Build Azure OpenAI dialogue generator
- [ ] Implement Speech TTS + segment export
- [ ] Stitch audio, apply music/metadata
- [ ] Add orchestration CLI, logging, docs
- [ ] Scaffold src tree, deps, env config
- [ ] Build Azure OpenAI dialogue generator
- [ ] Implement Speech TTS + segment export
- [ ] Stitch audio, apply music/metadata
- [ ] Add orchestration CLI, logging, docs
- [ ] Implement AI ingestion for supporting files
- [ ] Redesign GUI dashboard with run history
- [ ] Add slide-style video + ppt/pdf export
- [ ] Enhance cost tracker + GUI charts
- [ ] Update GUI layout, launch scripts, docs
- [ ] NotebookLM-style PyQt interface overhaul
- [ ] Gemini+Azure hybrid metadata chat flow
- [ ] Project hubs + visual analytics
- [ ] Advanced outputs (gallery/PDF/story)
- [ ] UX polish, budgets, onboarding
- [ ] Switch GUI font to Segoe UI 13pt
- [ ] Fix chat layout/alignment + Enter-to-send
- [ ] Rename output section + clarify run prefs