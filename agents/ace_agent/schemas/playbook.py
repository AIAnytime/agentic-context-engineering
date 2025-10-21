from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .delta import DeltaBatch, DeltaOperation


class Bullet(BaseModel):
    """Single playbook entry."""

    id: str
    section: str
    content: str
    helpful: int = 0
    harmful: int = 0
    neutral: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def tag(
        self, tag: Literal["helpful", "harmful", "neutral"], increment: int = 1
    ) -> None:
        current = getattr(self, tag)
        setattr(self, tag, current + int(increment))
        self.updated_at = datetime.now(timezone.utc).isoformat()


class Playbook(BaseModel):
    """Structured context store as defined by ACE."""

    bullets: Dict[str, Bullet] = Field(default_factory=dict)
    sections: Dict[str, List[str]] = Field(default_factory=dict)
    next_id: int = 0

    # ------------------------------------------------------------------ #
    # CRUD utils
    # ------------------------------------------------------------------ #
    def add_bullet(
        self,
        section: str,
        content: str,
        bullet_id: Optional[str] = None,
    ) -> Bullet:
        bullet_id = bullet_id or self._generate_id(section)
        bullet = Bullet(id=bullet_id, section=section, content=content)
        self.bullets[bullet_id] = bullet
        self.sections.setdefault(section, []).append(bullet_id)
        return bullet

    def update_bullet(
        self,
        bullet_id: str,
        content: str,
    ) -> Optional[Bullet]:
        bullet = self.bullets.get(bullet_id)
        if bullet is None:
            return None
        bullet.content = content
        bullet.updated_at = datetime.now(timezone.utc).isoformat()
        return bullet

    def remove_bullet(self, bullet_id: str) -> None:
        bullet = self.bullets.pop(bullet_id, None)
        if bullet is None:
            return
        section_list = self.sections.get(bullet.section)
        if section_list:
            self.sections[bullet.section] = [
                bid for bid in section_list if bid != bullet_id
            ]
            if not self.sections[bullet.section]:
                del self.sections[bullet.section]

    def update_bullet_tag(
        self,
        bullet_id: str,
        tag: Literal["helpful", "harmful", "neutral"],
        increment: int = 1,
    ) -> Optional[Bullet]:
        bullet = self.bullets.get(bullet_id)
        if bullet is None:
            return None
        bullet.tag(tag, increment=increment)
        return bullet

    def get_bullet(self, bullet_id: str) -> Optional[Bullet]:
        return self.bullets.get(bullet_id)

    def bullets_list(self) -> List[Bullet]:
        return list(self.bullets.values())

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, object]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Playbook":
        return cls.model_validate(payload)

    def dumps(self) -> str:
        # Use Pydantic JSON mode to ensure datetimes are ISO strings if present
        return self.model_dump_json(indent=2)

    @classmethod
    def loads(cls, data: str) -> "Playbook":
        return cls.model_validate_json(data)

    # ------------------------------------------------------------------ #
    # Delta application
    # ------------------------------------------------------------------ #
    def apply_delta(self, delta: DeltaBatch) -> None:
        for operation in delta.operations:
            self._apply_operation(operation)

    def _apply_operation(self, operation: DeltaOperation) -> None:
        op_type = operation.type.upper()
        if op_type == "ADD":
            self.add_bullet(
                section=operation.section,
                content=operation.content,
                bullet_id=operation.bullet_id,
            )
        elif op_type == "UPDATE":
            if operation.bullet_id is None:
                return
            self.update_bullet(
                bullet_id=operation.bullet_id,
                content=operation.content,
            )
        elif op_type == "REMOVE":
            if operation.bullet_id is None:
                return
            self.remove_bullet(operation.bullet_id)

    # ------------------------------------------------------------------ #
    # Presentation helpers
    # ------------------------------------------------------------------ #
    def as_prompt(self) -> str:
        """Return a human-readable playbook string for prompting LLMs."""
        parts: List[str] = []
        for section, bullet_ids in sorted(self.sections.items()):
            parts.append(f"## {section}")
            for bullet_id in bullet_ids:
                bullet = self.bullets[bullet_id]
                counters = f"(helpful={bullet.helpful}, harmful={bullet.harmful}, neutral={bullet.neutral})"
                parts.append(f"- [{bullet.id}] {bullet.content} {counters}")
        return "\n".join(parts)

    def stats(self) -> Dict[str, object]:
        return {
            "sections": len(self.sections),
            "bullets": len(self.bullets),
            "tags": {
                "helpful": sum(b.helpful for b in self.bullets.values()),
                "harmful": sum(b.harmful for b in self.bullets.values()),
                "neutral": sum(b.neutral for b in self.bullets.values()),
            },
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _generate_id(self, section: str) -> str:
        self.next_id += 1
        section_prefix = (section or "general").split()[0].lower()
        return f"{section_prefix}-{self.next_id:05d}"
