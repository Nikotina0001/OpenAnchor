# Using OpenAnchor

## Model and material setup

Use millimetres and place a watertight model on a planar bed at Z=0. Select a single unpainted positive part; painting, modifiers and unknown multipart assemblies are rejected. Configure two filament slots in a printer/profile that can switch materials. The flange uses the main material; the separate anchor and its support beams use the anchor material.

OpenAnchor checks configured temperature information where available. This is screening, not evidence of adhesion, removability or print success for a material pair.

## Normal and advanced anchors

Normal mode creates a model-adaptive flange and an overlapping anchor cap. Advanced mode adds anchor-material ribs from the bed, through matching flange slots, to the cap. Regular ribs follow the contour normal; sharp corners receive diagonal ribs. The model-clearance guard limits each ray to its first clear interval, preventing a distant wall from accepting a stray fragment behind another model branch.

Advanced defaults are 0.8 mm beam width, 10 mm spacing and 0.6 mm model clearance. Width and spacing must remain printable for the configured design line width. The validator rejects dimensions that leave insufficient flange support. Normal mode is the default and fallback when no supported beam layout fits.

The flange-to-object gap defaults to 0.1 mm and is a minimum horizontal gap over the projected lower wall envelope. It is not a constant 3D normal offset. Flange-to-anchor gap defaults to 0 mm and also controls beam-slot clearance. The reported native fitting tolerance can create microscopic clearance at nominal zero interfaces.

## Check, reset and suggestions

**Check settings** generates and validates a candidate without modifying or saving the project. If it fails, OpenAnchor tries defaults and a compact candidate while retaining material choices and advanced mode. **Use suggested settings** loads a passing candidate into the form; Apply or Export is still required. Physical performance is not checked.

**Reset settings** restores dimensions, enables anchor geometry and turns advanced mode off. It retains model/material choices, hardware confirmation and the resolved layer schedule. Form edits alone do not change the plate.

## Export 3MF

Export creates a fresh snapshot, validates the assembly and saves it under the plugin's private `exports` storage. The result displays the file path. Import it in Prepare **as one assembly**, keeping the original part, flange and anchor together. Current host configuration is copied where the audited API permits it; inspect the resulting printer/process/filament assignments. Standalone CLI geometry has no complete printer profile unless you supply one.

Exported flange parts carry **Wall loops = 100**. Native brim is disabled on the generated assembly to avoid duplicate brims. Disabling Include OpenAnchor geometry exports the source only; it does not remove previously imported geometry.

## Direct plate editing (optional custom build)

**Apply to plate** saves a unique project backup, then adds the flange and anchor to the selected object. The original source remains once. **Update anchor** replaces recorded generated parts; **Restore original** removes those parts and restores recorded original filament/brim overrides. Native edits record Undo actions.

After Apply or Update, set **Wall loops = 100** on **OpenAnchor flange** manually. The bridge cannot set this per-part override.

Ownership uses native object/volume IDs. Undo/Redo can recover recognized ID sets, but save/reopen may change IDs. Unknown assemblies are rejected rather than removed by name. Keep the pre-apply backup for recovery.

## Layers and Preview

For adaptive layers, supply the actual resolved layer-top list as JSON. The audited live Pages API cannot retrieve that graph. Constant-height objects use the current initial/object/process layer settings.

After slicing, inspect bed contact, flange slots, beam-to-model clearance, cap support, both materials, tool changes, purge/wipe tower and toolhead clearance. Use a small calibration specimen before attempting a real part. Synthetic test G-code is for offline checks and must not be printed.
