"""Persistence adapters."""

from uuid import UUID

from clean_app.domain.entities import User
from clean_app.domain.repositories import UserRepository


class InMemoryUserRepository(UserRepository):
    """In-memory implementation of UserRepository for development/testing."""

    def __init__(self) -> None:
        self._store: dict[UUID, User] = {}

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._store.get(user_id)

    def save(self, user: User) -> User:
        self._store[user.id] = user
        return user
