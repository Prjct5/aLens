from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Source = Literal["hatla2ee", "contactcars", "dubizzle"]
SOURCES: tuple[str, ...] = ("hatla2ee", "contactcars", "dubizzle")
ImageId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
PHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")]


def listing_key(source: str, source_listing_id: str) -> str:
    if source not in SOURCES:
        raise ValueError(f"unknown source: {source}")
    return f"{source}:{source_listing_id}"
