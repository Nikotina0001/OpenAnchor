# Dependency licenses

OpenAnchor code: AGPL-3.0-or-later. The unmodified AGPL license text was obtained from the audited OrcaSlicer revision's LICENSE.txt. No Orca C++ source is linked into or redistributed as part of this Python package.

| Dependency | Purpose | Upstream license |
|---|---|---|
| NumPy | mesh arrays and affine transforms | BSD-3-Clause |
| Shapely | polygon offsets, clipping, validity | BSD-3-Clause |
| GEOS (Shapely binary distribution) | robust polygon operations | LGPL-2.1-or-later |
| trimesh | STL/OBJ IO, mesh validation, extrusion | MIT |
| mapbox-earcut / Earcut | triangulation including holes | ISC |
| manifold3d / Manifold | manifold solids and booleans | Apache-2.0 |

These permit use with AGPL-3.0-or-later software subject to their notice and distribution obligations. Dependencies are declared as external packages rather than copied into this repository. Binary wheels, especially NumPy and Shapely, carry additional bundled-library notices; retain those when redistributing binaries. Review exact installed versions and their dist-info licenses when preparing a release. Build/test tools are not runtime dependencies. Third-party reference images and personal test models are excluded from the public release. The published geometry diagram is generated from the project's own calibration specimen. Native bridge patches derive from the pinned AGPL-licensed OrcaSlicer source; see native/README.md.
