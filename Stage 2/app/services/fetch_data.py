import random, requests
from datetime import datetime, timezone
from app import models
from sqlalchemy.orm import Session
from app.config import settings

# Centralize API URLs in settings (still overridable via .env)
COUNTRY_API: str = str(settings.COUNTRY_API)
EXCHANGE_API: str = str(settings.EXCHANGE_API)


def refresh_data(db: Session):
    """Fetch countries and exchange rates, compute GDPs, and upsert atomically.

    Returns False if external data sources are unavailable; DB remains unchanged.
    """
    # 1) Fetch external data first; abort on failure
    try:
        countries_resp = requests.get(COUNTRY_API, timeout=15)
        status = getattr(countries_resp, "status_code", 200)
        if status != 200:
            raise RuntimeError(f"Countries API returned {status}")
        countries_data = countries_resp.json()

        rates_resp = requests.get(EXCHANGE_API, timeout=15)
        status = getattr(rates_resp, "status_code", 200)
        if status != 200:
            raise RuntimeError(f"Exchange API returned {status}")
        rates_json = rates_resp.json()
        rates = rates_json.get("rates") or {}
    except Exception as e:
        print("Error fetching external data:", e)
        return False

    # 2) Apply updates in a single transaction; any error rolls back all writes
    try:
        with db.begin():
            for c in countries_data:
                name = c.get("name")
                pop = c.get("population")
                if not name or not pop:
                    continue

                curr_list = c.get("currencies", []) or []
                # Safely extract first currency code and normalize to upper
                currency_code = None
                for cur in curr_list:
                    code = (cur or {}).get("code")
                    if code and isinstance(code, str):
                        currency_code = code.upper()
                        break

                rate = None
                gdp = None

                if not curr_list or not currency_code:
                    # No currency — do not attempt rate lookup; set GDP to 0
                    currency_code = None
                    rate = None
                    gdp = 0
                else:
                    rate = rates.get(currency_code)
                    if rate:
                        gdp = (pop * random.randint(1000, 2000)) / rate
                    else:
                        # Currency present but rate missing
                        gdp = None

                existing = (
                    db.query(models.Country)
                    .filter(models.Country.name.ilike(name))
                    .first()
                )
                now_utc = datetime.now(timezone.utc)
                if existing:
                    existing.capital = c.get("capital")
                    existing.region = c.get("region")
                    existing.population = pop
                    existing.currency_code = currency_code
                    existing.exchange_rate = rate
                    existing.estimated_gdp = gdp
                    existing.flag_url = c.get("flag")
                    existing.last_refreshed_at = now_utc
                else:
                    db.add(
                        models.Country(
                            name=name,
                            capital=c.get("capital"),
                            region=c.get("region"),
                            population=pop,
                            currency_code=currency_code,
                            exchange_rate=rate,
                            estimated_gdp=gdp,
                            flag_url=c.get("flag"),
                            last_refreshed_at=now_utc,
                        )
                    )
        return True
    except Exception as e:
        print("Error refreshing DB:", e)
        return False
