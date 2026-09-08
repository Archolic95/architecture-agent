# Architecture modeling scripts

`geometry_kit.py` authors native polygonal Extrusions and matching preview meshes.
`cpu_preview.py` creates the existing uncapped display clips, and `viewer/`
provides the browser preview.

`native_sections.py` is an optional, separate filled 2D solid-section command.
Read [its scope, units and numerical policy](../references/native-sections.md)
before use. Its “material” regions mean combined solid occupancy, not
construction-material classifications. Original portable controls and their
20 focused tests are under `section_controls/`; their construction and
expectations are described in [the control reference](section_controls/controls/README.md).
