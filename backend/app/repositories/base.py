from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Thin data-access wrapper around a single SQLAlchemy model.

    Holds no business rules — isolation checks, validation, and orchestration
    across multiple models belong in the service layer, not here.
    """

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        self.db = db
        self.model = model

    def get(self, entity_id: int) -> ModelType | None:
        return self.db.get(self.model, entity_id)

    def list(self) -> list[ModelType]:
        return list(self.db.scalars(select(self.model)))

    def add(self, instance: ModelType) -> ModelType:
        self.db.add(instance)
        self.db.flush()
        self.db.refresh(instance)
        return instance

    def delete(self, instance: ModelType) -> None:
        self.db.delete(instance)
        self.db.flush()
