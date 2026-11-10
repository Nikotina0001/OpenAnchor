# Beta 1 verification

Version: **0.2.0b1** / tag **v0.2.0-beta.1**. Beta 1 packages the dev7 implementation; the release changes documentation and distribution metadata, not geometry behavior.

## Automated checks

The suite covers settings validation, bed/exclusion/obstacle checks, model transforms and preservation, mesh validity, solid intersections, layer alignment, 3MF metadata, flange wall loops, advanced beams, host API fixtures, ownership/apply/update/restore behavior and UI controls.

A facing-rectangle regression ensures beams cannot cross a neighboring object to reach a remote wall. The reported complex-model regression changed 91 placements to 82, retained 12 corner beams and measured minimum beam/model clearance of approximately 0.600236 mm. The personal input model and profiles are not redistributed.

GitHub Actions runs the Python suite and builds distributions on Windows and Ubuntu. These jobs do not run OrcaSlicer or print anything. The final local/public CI results are recorded in the beta release notes and action runs.

## Native checks

The audited native host is OrcaSlicer 2.5.0-beta revision `345efec64c7b95a05ce5cf96df0dde66a158835c`. Earlier isolated checks verified normal-anchor apply/update/restore, Undo/Redo and two-material Preview. Dev7 advanced geometry passed native CLI two-tool slicing and float-mesh validity checks. Embedded UI fixtures are not live host tests.

The optional bridge has five Catch2 regression cases in its patch; a new native rebuild is not part of Beta 1. Use `tests/verify_native.py` with an isolated compatible executable for calibration export/slice verification.

## Not verified

- Physical adhesion, removal, warpage reduction or material-pair performance.
- Live native GUI Preview and embedded button execution for the current advanced-beam release.
- Embedded plugin behavior on Linux/macOS or every newer Orca revision.
- Exhaustive arbitrary input-mesh self-intersections or swept toolhead collision safety.

Direct Apply still requires manual flange **Wall loops = 100**; 3MF export includes the override. Nominal zero interfaces use the recorded coordinate-dependent fit allowance. Synthetic test profiles/G-code are offline fixtures, not printable machine configurations.
