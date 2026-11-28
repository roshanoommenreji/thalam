"""What a load found wrong: each problem names its file and field (SPEC-002-R6)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    file: str  # relative to the company folder, with forward slashes
    field: str  # where in the file, such as "releases[1].events[2]"
    message: str  # file-provided values appear through repr(), so no control character prints

    def __str__(self) -> str:
        return f"{self.file}: {self.field}: {self.message}"


class LoadError(Exception):
    """One or more problems; a load that raises this has written nothing."""

    def __init__(self, problems: list[Problem]) -> None:
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems
