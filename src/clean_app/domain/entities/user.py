"""Domain entities — core business objects."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class User:
    """Represents a user in the system."""

    id: UUID
    email: str
    name: str
    created_at: datetime

    @classmethod
    def create(cls, email: str, name: str) -> "User":
        """Factory method to create a new user."""
        return cls(
            id=uuid4(),
            email=email,
            name=name,
            created_at=datetime.now(UTC),
        )
