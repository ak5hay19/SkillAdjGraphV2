"""Build failures. Every one of them stops the build before anything is installed (exit code 1)."""


class BuildError(Exception):
    """The curated build cannot be produced safely from these inputs."""


class TargetError(BuildError):
    """An overlay target_row_key does not resolve to exactly the rows its grammar names."""


class EvidenceError(BuildError):
    """Cited evidence cannot be resolved to an available source, or cannot substantiate an applied value."""
