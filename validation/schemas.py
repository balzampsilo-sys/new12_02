"""Pydantic schemas for input validation

This module provides comprehensive input validation using Pydantic v2.
All user inputs and critical operations are validated before processing.
"""

import re
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TimeSlotInput(BaseModel):
    """Validation for time slot (date + time)"""

    date: date = Field(..., description="Booking date")
    time: time = Field(..., description="Booking time (HH:MM)")

    @field_validator("time")
    @classmethod
    def validate_time_slot(cls, v: time) -> time:
        """Validate time is on hour boundary"""
        if v.minute != 0 or v.second != 0:
            raise ValueError("Time must be on the hour (e.g., 10:00, 14:00)")
        return v

    @model_validator(mode="after")
    def validate_not_past(self) -> "TimeSlotInput":
        """Validate datetime is not in the past"""
        dt = datetime.combine(self.date, self.time)
        if dt < datetime.now():
            raise ValueError("Cannot book slots in the past")
        return self

    def to_strings(self) -> tuple[str, str]:
        """Convert to string tuple (date_str, time_str)"""
        return self.date.isoformat(), self.time.strftime("%H:%M")


class BookingCreateInput(BaseModel):
    """Validation for creating a booking"""

    user_id: int = Field(..., gt=0, description="Telegram user ID")
    username: Optional[str] = Field(None, max_length=100, description="Telegram username")
    date: date = Field(..., description="Booking date")
    time: time = Field(..., description="Booking time")
    service_id: int = Field(default=1, gt=0, description="Service ID")
    duration_minutes: int = Field(default=60, ge=15, le=480, description="Duration in minutes")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize username"""
        if v:
            # Remove @ if present
            v = v.lstrip("@")
            # Only alphanumeric, underscore, dash
            if not re.match(r"^[a-zA-Z0-9_-]{3,32}$", v):
                raise ValueError("Invalid username format")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: time) -> time:
        """Validate time format"""
        if v.minute != 0 or v.second != 0:
            raise ValueError("Time must be on the hour")
        if not (9 <= v.hour < 18):  # Default work hours
            raise ValueError("Time must be within work hours")
        return v

    @model_validator(mode="after")
    def validate_booking(self) -> "BookingCreateInput":
        """Validate booking is not in past"""
        dt = datetime.combine(self.date, self.time)
        if dt < datetime.now():
            raise ValueError("Cannot create booking in the past")
        return self


class BookingCancelInput(BaseModel):
    """Validation for canceling a booking"""

    booking_id: int = Field(..., gt=0, description="Booking ID")
    user_id: int = Field(..., gt=0, description="User ID")
    reason: Optional[str] = Field(None, max_length=500, description="Cancellation reason")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize reason text"""
        if v:
            v = v.strip()
            if len(v) < 3:
                raise ValueError("Reason must be at least 3 characters")
        return v


class SlotBlockInput(BaseModel):
    """Validation for blocking a time slot"""

    date: date = Field(..., description="Date to block")
    time: time = Field(..., description="Time to block")
    admin_id: int = Field(..., gt=0, description="Admin user ID")
    reason: Optional[str] = Field(None, max_length=500, description="Block reason")

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: time) -> time:
        if v.minute != 0 or v.second != 0:
            raise ValueError("Time must be on the hour")
        return v

    @field_validator("reason")
    @classmethod
    def sanitize_reason(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize reason text"""
        if v:
            v = v.strip()
            # Remove excessive whitespace
            v = re.sub(r"\s+", " ", v)
        return v


class ServiceInput(BaseModel):
    """Validation for service creation/update"""

    name: str = Field(..., min_length=3, max_length=100, description="Service name")
    description: Optional[str] = Field(
        None, max_length=500, description="Service description"
    )
    duration_minutes: int = Field(..., ge=15, le=480, description="Duration (15-480 min)")
    price: Optional[str] = Field(None, max_length=50, description="Price string")
    is_active: bool = Field(default=True, description="Is service active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Sanitize service name"""
        v = v.strip()
        if not v:
            raise ValueError("Service name cannot be empty")
        # Remove excessive whitespace
        v = re.sub(r"\s+", " ", v)
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[str]) -> Optional[str]:
        """Validate price format"""
        if v:
            v = v.strip()
            # Allow formats: "1000", "1000 руб", "от 1000", "1000-2000"
            if not re.match(r"^[\d\s\-₽руб.a-zA-Zа-яА-Я]+$", v):
                raise ValueError("Invalid price format")
        return v


class AdminInput(BaseModel):
    """Validation for admin operations"""

    user_id: int = Field(..., gt=0, description="User ID")
    username: Optional[str] = Field(None, max_length=100, description="Username")
    role: str = Field(default="moderator", description="Admin role")
    added_by: Optional[int] = Field(None, gt=0, description="Added by admin ID")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate admin role"""
        allowed_roles = ["super_admin", "moderator"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize username"""
        if v:
            v = v.lstrip("@").strip()
            if v and not re.match(r"^[a-zA-Z0-9_-]{3,32}$", v):
                raise ValueError("Invalid username format")
        return v


class UserInput(BaseModel):
    """Validation for user data"""

    user_id: int = Field(..., gt=0, description="Telegram user ID")
    username: Optional[str] = Field(None, max_length=100, description="Username")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")

    @field_validator("username", "first_name", "last_name")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields"""
        if v:
            v = v.strip()
            # Remove control characters
            v = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", v)
            v = re.sub(r"\s+", " ", v)
        return v if v else None


class WorkHoursInput(BaseModel):
    """Validation for work hours configuration"""

    start_hour: int = Field(..., ge=0, le=23, description="Start hour (0-23)")
    end_hour: int = Field(..., ge=1, le=24, description="End hour (1-24)")

    @model_validator(mode="after")
    def validate_range(self) -> "WorkHoursInput":
        """Validate start < end"""
        if self.start_hour >= self.end_hour:
            raise ValueError("Start hour must be before end hour")
        if self.end_hour - self.start_hour < 2:
            raise ValueError("Work day must be at least 2 hours")
        return self


# === VALIDATION HELPERS ===


def validate_date_string(date_str: str) -> date:
    """Parse and validate date string (YYYY-MM-DD)

    Args:
        date_str: Date string in ISO format

    Returns:
        date object

    Raises:
        ValueError: If date format is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}") from e


def validate_time_string(time_str: str) -> time:
    """Parse and validate time string (HH:MM)

    Args:
        time_str: Time string in HH:MM format

    Returns:
        time object

    Raises:
        ValueError: If time format is invalid
    """
    try:
        parsed_time = datetime.strptime(time_str, "%H:%M").time()
        if parsed_time.minute != 0:
            raise ValueError("Time must be on the hour")
        return parsed_time
    except ValueError as e:
        raise ValueError(f"Invalid time format. Use HH:MM: {e}") from e


def sanitize_input(text: str, max_length: int = 500) -> str:
    """Sanitize user input text

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text

    Raises:
        ValueError: If text is too long
    """
    if not text:
        return ""

    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_length:
        raise ValueError(f"Text too long (max {max_length} characters)")

    return text
