import re
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


_ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_RESERVED_ALIASES = {
    "create",
}


class UrlCreateRequest(BaseModel):
    original_url: HttpUrl = Field(..., description="The original URL to be shortened")
    custom_alias: Optional[str] = Field(
        None, description="Optional custom alias for the short URL"
    )
    expire_in_days: Optional[int] = Field(
        None, ge=1, le=365, description="Number of days after which the URL will expire"
    )

    @field_validator("original_url")
    @classmethod
    def _validate_original_url(cls, v: HttpUrl) -> HttpUrl:
        s = str(v)
        if len(s) > 2048:
            raise ValueError("URL is too long")

        host = getattr(v, "host", None)
        if host and host.lower() in {"localhost"}:
            raise ValueError(
                "localhost URLs are not allowed (use the server LAN IP/hostname)"
            )

        return v

    @field_validator("custom_alias")
    @classmethod
    def _validate_custom_alias(cls, v: str | None) -> str | None:
        if v is None:
            return None
        alias = v.strip()
        if not alias:
            return None
        if alias.lower() in _RESERVED_ALIASES:
            raise ValueError("custom_alias is reserved")
        if not _ALIAS_RE.fullmatch(alias):
            raise ValueError("custom_alias must match ^[A-Za-z0-9_-]{3,32}$")
        return alias

    class Config:
        json_schema_extra = {
            "example": {
                "original_url": "https://www.example.com/some/long/path",
                "custom_alias": "myalias",
                "expire_in_days": 30,
            }
        }


class UrlCreateResponse(BaseModel):
    short_code: str = Field(..., description="The generated short code for the URL")
    long_url: HttpUrl = Field(..., description="The original long URL")

    class Config:
        json_schema_extra = {
            "example": {
                "short_code": "abc123",
                "long_url": "https://www.example.com/some/long/path",
            }
        }


class UrlResponse(BaseModel):
    short_code: str = Field(..., description="The short code for the URL")
    long_url: HttpUrl = Field(..., description="The original long URL")
    clicks: int = Field(
        0, description="Number of times the short URL has been accessed"
    )
    created_at: Optional[str] = Field(
        None, description="Timestamp when the short URl was created"
    )
    expires_at: Optional[str] = Field(
        None, description="Timestamp when the short URL will expire"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "short_code": "abc123",
                "long_url": "https://www.example.com/some/long/path",
                "clicks": 42,
                "created_at": "2024-01-01T12:00:00Z",
                "expires_at": "2024-01-31T12:00:00Z",
            }
        }


class UrlMetadataResponse(BaseModel):
    long_url: HttpUrl = Field(..., description="The original long URL")
    short_code: str = Field(..., description="The short code for the URL")
    clicks: int = Field(
        0, description="Number of times the short URl has been accessed"
    )
    created_at: Optional[str] = Field(
        None, description="Timestamp when the short URL was created"
    )
    expires_at: Optional[str] = Field(
        None, description="Timestamp when the short URL will expire"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "long_url": "https://www.example.com/some/long/path",
                "short_code": "abc123",
                "clicks": 42,
                "created_at": "2024-01-01T12:00:00Z",
                "expires_at": "2024-01-31T12:00:00Z",
            }
        }


class UrlResolveResponse(BaseModel):
    long_url: HttpUrl = Field(..., description="The original long URL")

    class Config:
        json_schema_extra = {
            "example": {"long_url": "https://www.example.com/some/long/path"}
        }


class UrlErrorResponse(BaseModel):
    detail: str = Field(
        ..., description="Error message detailing the issue with the URL operation"
    )

    class Config:
        json_schema_extra = {
            "example": {"detail": "The provided short code does not exist."}
        }
