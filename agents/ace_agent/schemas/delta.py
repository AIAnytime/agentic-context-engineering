from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Allowed operation types for curator delta mutations
OperationType = Literal["ADD", "UPDATE", "REMOVE"]


class DeltaOperation(BaseModel):
    """Single mutation to apply to the playbook."""

    model_config = ConfigDict(extra="ignore")

    type: OperationType
    section: str
    content: Optional[str] = None
    bullet_id: Optional[str] = None

    @classmethod
    def from_json(cls, payload: dict) -> "DeltaOperation":
        # Use Pydantic v2 API for concise validation from arbitrary dicts
        return cls.model_validate(payload)

    def to_json(self) -> dict:
        # Keep payload lean by dropping None fields
        return self.model_dump(exclude_none=True)


class DeltaBatch(BaseModel):
    """Bundle of curator reasoning and delta operations."""

    model_config = ConfigDict(extra="ignore")

    reasoning: str
    operations: List[DeltaOperation] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict) -> "DeltaBatch":
        return cls.model_validate(payload)

    @classmethod
    def from_json(cls, payload: dict) -> "DeltaBatch":
        return cls.model_validate(payload)

    def to_json(self) -> dict:
        return self.model_dump(exclude_none=True)
