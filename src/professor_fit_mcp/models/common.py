from typing import Any, Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low", "unknown"]


class SourcedField(BaseModel):
    """A value with provenance tracking."""

    value: Any = None
    sources: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"
