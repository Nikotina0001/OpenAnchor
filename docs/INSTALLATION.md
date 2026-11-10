# Installation

## Requirements

- A compatible OrcaSlicer build with Python plugins and the Pages API. Beta 1 was developed on Windows x64 with OrcaSlicer 2.5.0-beta revision `345efec64c7b95a05ce5cf96df0dde66a158835c`.
- The host's Python 3.12+ environment must be able to resolve NumPy, Shapely, trimesh, Manifold and mapbox-earcut from its package index. The wheel declares these dependencies; it does not bundle them.
- Two loaded filament slots and hardware/profile support for material switching.

Other host revisions and embedded runtimes are not certified by this beta. See the [upstream plugin guide](https://github.com/OrcaSlicer/OrcaSlicer/wiki/plugins_getting_started).

## Download and install

1. Open [Beta 1](https://github.com/Nikotina0001/OpenAnchor/releases/tag/v0.2.0-beta.1).
2. Under Assets, download `openanchor-0.2.0b1-py3-none-any.whl`. Use `SHA256SUMS.txt` to verify it if desired. The `.tar.gz` and automatic source archives are for development.
3. Save any open project. In OrcaSlicer's Plugins window, choose **Browse plugins → Install local plugin** and select the wheel.
4. Allow dependency installation and activate the OpenAnchor Pages capability. Restart OrcaSlicer.
5. Open **OpenAnchor**, configure your real printer/materials, load a model and Refresh.

No system-wide Python installation is needed for wheel installation when the host has a working embedded plugin runtime. Building from source requires Python.

## Which plate workflow is available?

**Audited stock build:** use Export 3MF, then import the export as one assembly. Apply / Update / Restore are disabled when the native bridge is absent.

**OpenAnchor-enabled build:** the plugin detects `apply_anchor`, `restore_anchor` and `instance_plate` bindings and enables direct editing. Build this edition separately using [the native source patches](../native/README.md). This beta does not ship a custom Orca binary or automatically patch your installation.

## Updating

Save projects and retain backups. Install the new wheel using the host's local install/update action and restart. If a build treats differently named wheels as separate plugins, disable the older OpenAnchor entry before enabling the new one. Do not run two copies against the same project. Keep the old wheel for rollback; do not delete private settings or ownership records during an update.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No Plugins menu or no OpenAnchor tab | Confirm the build includes Python plugins and Pages; enable the capability and restart. |
| Dependency installation fails | Inspect Plugins → Diagnostics. Confirm network/package-index access and compatible Python/platform wheels. |
| Apply is unavailable | Expected without the optional native bridge. Export 3MF remains the fallback. |
| Model is rejected | Use one watertight, unpainted positive part, on the bed. Direct editing also requires one instance. |
| No valid suggestion | Bed space, obstacles or geometry may prevent a valid layout; adjust placement/dimensions or use normal mode. |
| Imported parts separate or wrong material | Reimport as one assembly, keep all three volumes together and check part filament assignments. |
| Restore is unavailable after reopening | Native IDs may have changed. Recover from the saved pre-apply project backup. |

For a report, include your OS, Orca build, plugin version, steps and a minimal shareable model. Remove credentials, personal paths, serial numbers and private profile data from logs before posting.
