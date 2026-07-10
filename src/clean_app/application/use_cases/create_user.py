"""Application use cases."""

from clean_app.application.dto import CreateUserRequest, UserResponse
from clean_app.domain.entities import User
from clean_app.domain.repositories import UserRepository


class CreateUserUseCase:
    """Create a new user."""

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    def execute(self, request: CreateUserRequest) -> UserResponse:
        user = User.create(email=request.email, name=request.name)
        saved = self._user_repository.save(user)
        return UserResponse(
            id=str(saved.id),
            email=saved.email,
            name=saved.name,
        )
