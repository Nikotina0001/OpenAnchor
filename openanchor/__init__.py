"""Reusable engine; register a capability only inside OrcaSlicer's interpreter."""
__version__ = "0.2.0b1"

try:
    import orca
except ModuleNotFoundError as exc:
    if exc.name != "orca":
        raise
else:
    from .plugin import OpenAnchorPage

    @orca.plugin
    class OpenAnchor(orca.base):
        def register_capabilities(self):
            orca.register_capability(OpenAnchorPage)
