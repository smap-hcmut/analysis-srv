"""Base schemas for API responses."""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Metadata included in all API responses."""

    timestamp: datetime = Field(description="Response timestamp in UTC")
    request_id: str = Field(description="Unique request ID for tracing")
    version: str = Field(default="v1", description="API version")


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")
    total_items: int = Field(description="Total number of items")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages")
    has_prev: bool = Field(description="Whether there are previous pages")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = Field(description="Indicates if request was successful")
    data: T = Field(description="Response data")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response wrapper."""

    success: bool = Field(description="Indicates if request was successful")
    data: List[T] = Field(description="List of response items")
    meta: PaginationInfo = Field(description="Pagination metadata")


class ListResponseMeta(BaseModel):
    """Metadata for list responses without pagination."""

    total: int = Field(description="Total number of items matching the filter")


class ListResponse(BaseModel, Generic[T]):
    """List API response wrapper without pagination."""

    success: bool = Field(description="Indicates if request was successful")
    data: List[T] = Field(description="List of response items")
    meta: ListResponseMeta = Field(description="Response metadata with total count")


class ErrorDetail(BaseModel):
    """Individual error detail."""

    field: str = Field(description="Field name that caused the error")
    message: str = Field(description="Error message")
    code: str = Field(description="Error code")


class ErrorInfo(BaseModel):
    """Error information for failed responses."""

    code: str = Field(description="Application error code")
    message: str = Field(description="Human-readable error message")
    details: List[ErrorDetail] = Field(default=[], description="Detailed error information")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    success: bool = Field(default=False, description="Always false for error responses")
    error: ErrorInfo = Field(description="Error information")
    meta: ResponseMeta = Field(description="Response metadata")


class FilterParams(BaseModel):
    """Base filter parameters for all endpoints."""

    project_id: UUID = Field(description="Project ID (required)")
    brand_name: Optional[str] = Field(default=None, description="Filter by brand name")
    keyword: Optional[str] = Field(default=None, description="Filter by keyword")


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class DateRangeParams(BaseModel):
    """Date range filter parameters."""

    from_date: Optional[datetime] = Field(default=None, description="Start date (inclusive)")
    to_date: Optional[datetime] = Field(default=None, description="End date (inclusive)")


def create_response_meta(request_id: str) -> ResponseMeta:
    """Create response metadata with current timestamp."""
    return ResponseMeta(timestamp=datetime.utcnow(), request_id=request_id, version="v1")


def create_pagination_info(page: int, page_size: int, total_items: int) -> PaginationInfo:
    """Create pagination info from parameters."""
    total_pages = (total_items + page_size - 1) // page_size  # Ceiling division

    return PaginationInfo(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def create_list_response_meta(total: int) -> ListResponseMeta:
    """Create response metadata for list responses with total count."""
    return ListResponseMeta(total=total)
