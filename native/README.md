# OpenAnchor native plate bridge

Base: OrcaSlicer revision `345efec64c7b95a05ce5cf96df0dde66a158835c` (2.5.0-beta).

`openanchor-plate-bridge.patch` adds the two native Plater editing methods used by the Python plugin. Apply it to a clean checkout of that revision with `git apply`. It includes the staging helper and five Catch2 regression cases under `[AnchorPlateEdit]`.

`windows-build-fixes.patch` fixes the dependency checkout for the pinned wxWidgets revision and applies the OCCT patch from its source directory, so a dependency build outside the repository works. Apply it before configuring dependencies. Use a native Windows Perl such as portable Strawberry Perl; Git's Cygwin Perl cannot configure the MSVC OpenSSL build.

Use upstream `build_win.bat -d -s --tests --vs 2022 --msvc --no-gettext -i -j 2` with dedicated `--deps-dir` and `--build-dir` directories, CMake and Perl on PATH. Build Tools must include the C++ workload and Windows SDK. Keep the output application separate from the installed application.

The bridge stages a detached object copy and validates meshes, IDs, ownership and filament slots before taking an Undo snapshot and swapping the object. The source object's ID, original part, instance transform and unrelated model objects are preserved. Generated world-space meshes are transformed into object coordinates, including mirror handling. Restore removes only the two expected generated volumes and restores inheritance when the original settings had no explicit override.

`Plater.instance_plate(object_id, instance)` returns the selected instance's plate index and world origin. The plugin uses this to translate printable-bed and exclusion polygons for later plates; mesh generation remains in world coordinates.

The plugin must not retain or read old native object/volume handles after an edit. Ownership is returned as plain IDs and settings, then persisted by the plugin. Unknown multipart models and multiple instances are rejected. Live native apply/update/restore, Undo/Redo, two-material Preview and saved-project native slicing pass in the isolated calibration test. Embedded HTML clicks and physical printing remain unverified; see `../docs/VERIFICATION.md`.
