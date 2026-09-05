from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrintJobRequest(StrictRequest):
    source: str = Field(min_length=1, max_length=16)
    pages: Optional[int] = Field(default=None, ge=1, le=15)


class PingRequest(StrictRequest):
    source: str = Field(min_length=1, max_length=16)
    destination: str = Field(min_length=1, max_length=16)


class DiagnosticRequest(PingRequest):
    diagnostic_type: Literal["ping", "reachability", "traceroute", "dns", "service-health"]


class EmployeeDraft(StrictRequest):
    given_name: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z '-]*$")
    surname: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z '-]*$")
    role: str = Field(min_length=2, max_length=64)
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9.]+$")


class WorkstationDraftRequest(StrictRequest):
    device_type: Literal["workstation", "laptop"] = "workstation"
    floor: Literal["access_01", "access_02", "access_03"]
    hostname: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern=r"^(WS|LTP)[0-9]{2,4}$")


class ApplyDraftRequest(StrictRequest):
    draft_id: str = Field(min_length=16, max_length=64)


class EmployeeCreateRequest(StrictRequest):
    workstation: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern=r"^(WS|LTP)[0-9]{2,4}$")
    employee: EmployeeDraft


class EmployeeAssignmentRequest(StrictRequest):
    workstation: str = Field(min_length=4, max_length=12, pattern=r"^(WS|LTP)[0-9]{2,4}$")


class FileAccessCheckRequest(StrictRequest):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9.]+$")
    device: str = Field(min_length=4, max_length=12, pattern=r"^(WS|LTP)[0-9]{2,4}$")
    share: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9-]*$")
    operation: Literal["read", "write"] = "read"


class FileServerFaultRequest(StrictRequest):
    share: Optional[str] = Field(default=None, min_length=2, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9-]*$")


class FileShareMembershipRequest(StrictRequest):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9.]+$")
    group: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9-]*$")
    action: Literal["add", "remove"]
