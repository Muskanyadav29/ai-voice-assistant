"""Domain repository interfaces (ports)."""

from abc import ABC, abstractmethod
from uuid import UUID

from clean_app.domain.entities import User


class UserRepository(ABC):
    """Abstract user repository — implemented in infrastructure layer."""

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None:
        """Retrieve a user by ID."""

    @abstractmethod
    def save(self, user: User) -> User:
        """Persist a user."""
