# Contributing to OpenAnchor

Bug reports, compatibility results and focused pull requests are welcome. Use the issue forms and include the plugin/Orca/OS versions, steps, expected behavior and actual result. Share a minimal model only if you have permission to redistribute it. Remove private paths, printer credentials and personal data from diagnostics.

Keep changes small and preserve source geometry, world transforms and material assignments. Use the existing separation between geometry, settings, export, host integration and UI. Keep millimetres, XY bed coordinates and Z=0 contact explicit. In advanced mode, anchor-material beams may pass through flange slots; solids must remain disjoint and beams must clear the model.

Add a regression for geometry or state changes and run `python -m pytest -q` plus `python -m build`. For native work, use the pinned revision and separate build in `native/README.md`; never replace a user's installed slicer or unsaved project. Do not add speculative bindings, automatic publishing, G-code rewriting or unnecessary dependencies.

State exactly what was checked: API mocks, geometry, native slicing, GUI behavior and physical prints are separate evidence. Do not claim improved warpage performance without a reproducible physical experiment. Retain source/dependency licenses and notices.

Contributions are provided under the project's AGPL-3.0-or-later license.
