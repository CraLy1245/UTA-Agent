from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Alembic can discover the complete metadata graph.
from services.api.app.db import models as models  # noqa: E402, F401
