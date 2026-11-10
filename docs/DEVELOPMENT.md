# Development

## Setup

Use Python 3.12+ and an isolated virtual environment. Install `.[test]` as shown in the README. Runtime dependencies remain external packages; no additional UI framework or database is used.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build
.\.venv\Scripts\python.exe examples\make_specimens.py
```

On Linux/macOS, use `.venv/bin/python` in place of the Windows interpreter path. Generated example files are reproducible calibration geometry, not printer-ready profiles.

## Architecture

| Module | Responsibility |
| --- | --- |
| `settings.py` | Units, finite/range validation, slot and layer constraints |
| `geometry.py` | Footprint projection, solid construction, transforms and intersection checks |
| `beams.py` | Local contour-normal and corner beam placement |
| `materials.py` | Configured temperature/compatibility screening |
| `assembly_io.py` | Atomic 3MF export, filament metadata and aligned STL export |
| `plugin.py` | Host snapshots, settings/ownership records and plate/export operations |
| `page.html` | Pages interface and messages |
| `cli.py` | Standalone STL/OBJ entry point |
| `native/` | Optional pinned OrcaSlicer bridge patches |

Keep the geometry engine independent of the `orca` host module. No database or schema migrations are involved.

## Standalone CLI

```powershell
.\.venv\Scripts\python.exe -m openanchor.cli examples\calibration-bar.stl --config examples\pp-candidate.json --output examples\generated.3mf --stls examples\generated-stls
```

Example bed geometry, temperatures, material names and hardware confirmations are illustrative. Replace them with a real setup before any physical print. Do not CLI-slice a geometry-only 3MF with incomplete multi-filament defaults; the audited Orca beta can crash on incomplete profiles. Import it into a correctly configured GUI project or supply a complete compatible `slicer_project` in the CLI JSON. Relative project paths resolve beside that configuration file.

## Optional native integration test

Generate specimens first, then run:

```powershell
.\.venv\Scripts\python.exe tests\verify_native.py --orca '<path-to-orca-executable>'
```

This uses an isolated `.audit` data directory and a synthetic two-tool profile. It checks native slicing and writes a local verification report. Never send the generated G-code to a printer. Native GUI checks and physical printing remain separate validation steps.

## Release convention

Beta 1 uses tag `v0.2.0-beta.1`, Python version `0.2.0b1` and a GitHub **prerelease**. Update package version, `__version__`, UI badge and changelog together. Run tests, build wheel/source distribution, inspect archive contents, then publish both with SHA-256 checksums. Verify hosted CI and uploaded checksums. Publishing requires an explicit maintainer action; push CI only tests and builds artifacts.
