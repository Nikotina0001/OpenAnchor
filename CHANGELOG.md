# Changelog

## 0.2.0 Beta 1 — 2026-11-10

First public beta, packaged as `0.2.0b1` and tagged `v0.2.0-beta.1`.

- Publish the existing dev7 geometry engine, Pages interface and optional native bridge source patches.
- Include normal and advanced anchors, model-adaptive flange clearance, reset and geometry-checked suggestions.
- Carry the stray-beam correction: stop at the first model-clearance obstruction.
- Add public installation, usage, compatibility, verification and contribution guides.
- Provide a plugin wheel, source distribution and SHA-256 checksums.
- No new geometry behavior or native application rebuild in this release.

## 0.2.0.dev7 — 2026-11-07

- Stop contour-normal beams at the first model-clearance obstruction; never attach a clipped fragment to a remote wall.
- Warping-Test retains 82 placements and all 12 corner beams; nine stray placements removed.
- 82 Python tests pass, including close-facing model branches; native two-tool slicing passes.

## 0.2.0.dev6 — 2026-11-07

- Added optional Advanced anchor with bed-to-cap beams through flange slots: corners plus regular contour-normal spacing.
- Added beam width, spacing and model-clearance controls to save/reset/check/suggestions.
- Stabilized native float meshes and exact decimal validation boundaries.
- 81 Python tests pass; Warping-Test advanced assembly has 91 beams (12 corners) and slices with both tools.
- Plugin-only update; no native executable changes or physical performance claim.

## 0.2.0.dev5 — 2026-10-30

- Added independent Flange-to-object gap, default 0.1 mm, including Reset and checked suggestions.
- Positive gap clears the projected lower wall through flange height; zero keeps the previous conforming contact geometry.
- Reject gaps that leave insufficient clamp support; note reduced retention from separating the flange.
- 58 tests pass; Warping-Test measures 0.1 mm clearance and slices in native Orca.

## 0.2.0.dev4 — 2026-10-30

- Adapted the anchor outline to actual model geometry from the bed to the clamp top.
- Subtract the unchanged source solid from the flange where lower walls slope outward.
- Retained bed contact, collision, clearance and original-hole checks.
- Warping-Test.3MF passes generation and native two-tool slicing; 47 regression tests pass.

## 0.2.0.dev3 — 2026-10-30

- Added Reset settings for default dimensions without changing model, filament choices or layer schedule.
- Added read-only Check settings and geometry-verified default/compact suggestions.
- Added Use suggested settings; editing invalidates earlier check feedback.
- Plugin-only update; no Orca executable changes.

## 0.2.0.dev2 — 2026-10-30

- Changed the default flange-to-anchor gap to 0 mm.
- Exported 3MF flange parts now override Wall loops to 100 while preserving original-part settings.
- Direct Apply explains the existing bridge cannot set per-part Wall loops; set the flange to 100 manually in OrcaSlicer. No Orca application changes.

## 0.2.0.dev1 â€” in development

- Added capability-gated Apply to plate, Update anchor and Restore original controls.
- Shared geometry generation between direct edits and optional 3MF export.
- Saved unique pre-apply project backups and exact-ID ownership history for native Undo/Redo.
- Added native bridge patch with staged object edits, original setting restoration and Catch2 cases.
- Compiled and installed a separate custom OrcaSlicer build; live native apply/update/restore, Undo/Redo, Preview and saved-project two-tool slicing pass.
- Fixed native empty bed-exclusion sentinels and arbitrary polygon handling; 38 Python tests pass.
- Direct editing remains experimental and requires the custom build; embedded HTML clicks and physical printing are not verified.


## 0.1.1 â€” 2026-10-29

- Reworked the plugin page around object/material selection, flange and anchor settings, with advanced options collapsed.
- Added an explanatory cross-section and live requested-dimension readout, theme-aware colours and responsive layout.
- Added linked field errors, accessible status feedback, busy states and explicit missing-object/material guidance.
- Export results show requested/effective dimensions, a selectable path and clear Prepare/Preview instructions; refreshing preserves unsaved edits and selection.
- Geometry, host message contracts and export behaviour remain unchanged.

## 0.1.0 â€” 2026-10-29

- External continuous flange, independent solid anchor and upper cap with layer-aligned adjustable heights.
- Bed-contact mesh footprint, holes/islands, affine placement, mirrored winding and solid collision checks.
- Loaded-slot validation, preliminary thermal screening and stable material-assigned 3MF assembly export.
- Real Orca Pages capability and standalone CLI; generation leaves active project untouched.
- Geometry, export and host-contract tests; reproducible calibration models and optional native two-tool slicing verification.
- Export/import milestone only; no automatic native model insertion or physical performance claim.
