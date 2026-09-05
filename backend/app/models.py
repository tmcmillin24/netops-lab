from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrintJobRequest(StrictRequest):
    source: str = Field(min_length=1, max_length=16)
    pages: Optional[int] = Field(default=None, ge=1, le=15)


class PingRequest(StrictRequest):
    source: str = Field(min_length=1, max_length=16)
    destination: str = Field(min_length=1, max_length=16)
