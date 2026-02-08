from __future__ import annotations

from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from app.models import DataSource


def list_data_sources(db: Session) -> list[DataSource]:
    stmt = select(DataSource).order_by(desc(DataSource.created_at))
    return list(db.scalars(stmt))


def get_data_source(db: Session, data_source_id: int) -> DataSource | None:
    return db.get(DataSource, data_source_id)


def create_data_source(db: Session, name: str, type_: str, config_encrypted: str) -> DataSource:
    ds = DataSource(name=name, type=type_, config_encrypted=config_encrypted, is_active=False)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def update_data_source(
    db: Session,
    data_source_id: int,
    *,
    name: str | None = None,
    type_: str | None = None,
    config_encrypted: str | None = None,
) -> DataSource | None:
    ds = get_data_source(db, data_source_id)
    if not ds:
        return None
    if name is not None:
        ds.name = name
    if type_ is not None:
        ds.type = type_
    if config_encrypted is not None:
        ds.config_encrypted = config_encrypted
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def activate_data_source(db: Session, data_source_id: int) -> DataSource | None:
    ds = get_data_source(db, data_source_id)
    if not ds:
        return None

    # Deactivate others then activate this one. Unique partial index enforces the invariant too.
    db.execute(update(DataSource).values(is_active=False))
    db.execute(update(DataSource).where(DataSource.id == data_source_id).values(is_active=True))
    db.commit()
    db.refresh(ds)
    return ds


def delete_data_source(db: Session, data_source_id: int) -> bool:
    ds = get_data_source(db, data_source_id)
    if not ds:
        return False
    db.delete(ds)
    db.commit()
    return True
