from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_or_create(self, email: str, plan: str = "free") -> User:
        user = self.get_by_email(email)
        if user:
            return user
        user = User(email=email, plan=plan)
        self.db.add(user)
        self.db.flush()
        return user

    def count(self) -> int:
        return len(self.db.scalars(select(User.id)).all())
