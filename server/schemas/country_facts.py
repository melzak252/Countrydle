from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.user import UserDisplay


class CountryFactCountry(BaseModel):
    id: int
    name: str
    official_name: str | None = None


class LocalFactEntity(BaseModel):
    id: int
    name: str


class ScalarCountryFact(BaseModel):
    relation: str
    column: str
    value_type: str
    value: Any = None


class ListCountryFactValue(BaseModel):
    value: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ListCountryFact(BaseModel):
    relation: str
    table: str
    value_column: str
    metadata_columns: list[str] = Field(default_factory=list)
    values: list[ListCountryFactValue] = Field(default_factory=list)


class CountryFactsResponse(BaseModel):
    game_type: str | None = None
    entity: LocalFactEntity | None = None
    country: CountryFactCountry
    scalar_facts: list[ScalarCountryFact]
    list_facts: list[ListCountryFact]


class ScalarFactUpdate(BaseModel):
    game_type: str = "countrydle"
    entity_id: int | None = None
    country_id: int | None = None
    relation: str
    value: Any = None
    note: str | None = None


class ListFactCreate(BaseModel):
    game_type: str = "countrydle"
    entity_id: int | None = None
    country_id: int | None = None
    relation: str
    value: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class ListFactDelete(BaseModel):
    game_type: str = "countrydle"
    entity_id: int | None = None
    country_id: int | None = None
    relation: str
    value: str
    note: str | None = None


class CountryFactChangeLogDisplay(BaseModel):
    id: int
    user_id: int | None
    game_type: str = "countrydle"
    entity_id: int | None = None
    entity_name: str | None = None
    country_id: int
    country_name: str
    relation: str
    operation: str
    old_value: str | None
    new_value: str | None
    sqlite_table: str
    sqlite_column: str
    note: str | None
    server_version: str | None
    created_at: datetime
    user: UserDisplay | None = None

    model_config = ConfigDict(from_attributes=True)
