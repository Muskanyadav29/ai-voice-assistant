"""Data transfer objects for application layer."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateUserRequest:
    """Input for creating a user."""

    email: str
    name: str


@dataclass(frozen=True, slots=True)
class UserResponse:
    """Output representing a user."""

    id: str
    email: str
    name: str
