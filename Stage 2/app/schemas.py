from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CountryBase(BaseModel):
    name: str = Field(..., max_length=100)
    capital: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=50)
    population: int = Field(..., gt=0)
    currency_code: Optional[str] = Field(None, max_length=10)
    exchange_rate: Optional[float] = Field(None, gt=0)
    estimated_gdp: Optional[float] = Field(None, ge=0)
    flag_url: Optional[str] = Field(None, max_length=255)
    last_refreshed_at: Optional[datetime] = Field(None)

    model_config = {"from_attributes": True}


class CountryOut(CountryBase):
    id: int
