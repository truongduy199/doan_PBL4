"""User and Vehicle Domain Entities."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import AccountStatus, UserRole


@dataclass
class User:
    user_id: int
    username: str
    password_hash: str
    display_name: Optional[str]
    role: UserRole
    status: AccountStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class Vehicle:
    vehicle_id: int
    user_id: int
    plate_number: str
    status: AccountStatus
    created_at: datetime
    updated_at: datetime
