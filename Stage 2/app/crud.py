from sqlalchemy.orm import Session
from app import models

def get_country(db: Session, name: str):
    return db.query(models.Country).filter(models.Country.name.ilike(name)).first()

def get_countries(db: Session, region=None, currency=None, sort=None, limit=None, offset=None):
    query = db.query(models.Country)
    if region is not None:
        trimmed = region.strip()
        if not trimmed:
            return []
        pattern = trimmed if ("%" in trimmed or "_" in trimmed) else f"%{trimmed}%"
        query = query.filter(models.Country.region.ilike(pattern))
    if currency:
        query = query.filter(models.Country.currency_code.ilike(currency))

    if sort == "gdp_desc":
        query = query.order_by(models.Country.estimated_gdp.desc())
    elif sort == "gdp_asc":
        query = query.order_by(models.Country.estimated_gdp.asc())
    elif sort == "population_desc":
        query = query.order_by(models.Country.population.desc())
    elif sort == "population_asc":
        query = query.order_by(models.Country.population.asc())
    elif sort == "name_asc":
        query = query.order_by(models.Country.name.asc())
    elif sort == "name_desc":
        query = query.order_by(models.Country.name.desc())

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query.all()

def delete_country(db: Session, name: str):
    country = get_country(db, name)
    if country:
        db.delete(country)
        db.commit()
        return True
    return False


# -----------------------------
# App-level metadata operations
# -----------------------------
def get_last_refresh(db: Session):
    meta = db.query(models.RefreshMeta).filter(models.RefreshMeta.id == 1).first()
    return meta.last_refreshed_at if meta else None


def set_last_refresh(db: Session, dt):
    meta = db.query(models.RefreshMeta).filter(models.RefreshMeta.id == 1).first()
    if meta is None:
        meta = models.RefreshMeta(id=1, last_refreshed_at=dt)
        db.add(meta)
    else:
        meta.last_refreshed_at = dt
    db.commit()
    return meta.last_refreshed_at
