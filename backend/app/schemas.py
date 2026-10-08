"""Public API contracts: currency is explicit and decimal values retain precision."""

import re
import math
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The first release implements these currencies explicitly; conversion is not implied.
SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "JPY", "AED"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value):
        # Password whitespace is meaningful; reject it at the boundaries instead of silently changing it.
        if isinstance(value, str) and value != value.strip():
            raise ValueError("Password must not start or end with whitespace.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        value = value.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class PortfolioMetadata(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class PriceInput(StrictModel):
    date: date
    asset: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    price: float = Field(ge=1e-8, le=1e12, allow_inf_nan=False)


class AllocationInput(StrictModel):
    asset: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    weight: float = Field(ge=0, le=1, allow_inf_nan=False)


class PortfolioInput(StrictModel):
    scenario_name: str = Field(default="Base allocation", min_length=1, max_length=120)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    allocations: list[AllocationInput] = Field(min_length=1, max_length=20)
    prices: list[PriceInput] = Field(min_length=3, max_length=20000)
    rebalancing: str = Field(default="buy_and_hold", pattern=r"^(buy_and_hold|monthly)$")
    annualization_factor: int = Field(default=252, ge=1, le=366)
    risk_free_annual: float = Field(default=0, gt=-1, le=1, allow_inf_nan=False)
    benchmark_asset: str | None = Field(default=None, max_length=40)
    source: str = Field(default="User CSV", min_length=1, max_length=200)
    adjustment_method: str = Field(default="total_return", pattern=r"^(total_return|price_only)$")
    stress_shocks: dict[str, float] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def coherent_data(self):
        assets = [a.asset for a in self.allocations]
        if len(set(assets)) != len(assets) or abs(sum(a.weight for a in self.allocations) - 1) > 1e-8:
            raise ValueError("Use distinct assets with weights summing to 1.")
        pairs = [(p.date, p.asset) for p in self.prices]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Duplicate asset/date price observation.")
        needed = set(assets) | ({self.benchmark_asset} if self.benchmark_asset else set())
        calendars = [{p.date for p in self.prices if p.asset == asset} for asset in needed]
        if not calendars or len(calendars[0]) < 3 or any(c != calendars[0] for c in calendars):
            raise ValueError(
                "Every allocated asset and benchmark must have the same dates and at least three prices. Missing prices are not filled."
            )
        if set(p.asset for p in self.prices) - needed:
            raise ValueError("Remove unused assets or select them as allocations/benchmark.")
        if any(a not in assets or not math.isfinite(v) or not -1 <= v <= 1 for a, v in self.stress_shocks.items()):
            raise ValueError("Stress shocks must reference allocated assets and lie between -1 and 1.")
        return self


class ComparisonInput(StrictModel):
    analysis_ids: list[str] = Field(min_length=2, max_length=10)

    @field_validator("analysis_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Choose distinct analyses for comparison.")
        return values


class CsvPreviewInput(StrictModel):
    csv_text: str = Field(min_length=1, max_length=500000)
