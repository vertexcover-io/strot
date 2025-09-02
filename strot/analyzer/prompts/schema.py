from pydantic import BaseModel

from strot.schema.point import Point

__all__ = ("StepResult", "PaginationKeys", "ParameterDetectionResult")


class StepResult(BaseModel):
    """
    Args:
        close_overlay_popup_coords: Coordinates of dismiss button for overlay popups (cookie banners, modals, ads) that block content. Only set if popup is NOT related to user requirements.
        skip_to_content_coords: Coordinates of element or button which might lead to the required content.
        load_more_content_coords: Coordinates of pagination controls (Next, More, page numbers, arrows) that load additional relevant content.
        text_sections: List of exact text strings visible in screenshot that match user requirements (product names, prices, descriptions, etc.).
    """

    close_overlay_popup_coords: Point | None = None
    skip_to_content_coords: Point | None = None
    load_more_content_coords: Point | None = None
    text_sections: list[str] | None = None


class PaginationKeys(BaseModel):
    """
    Args:
        page_number_key: The key used to specify the page number for page-based pagination (e.g., 'page', 'page_no', 'page_number').
        limit_key: The key used to specify the maximum number of items to return per page (e.g., 'limit', 'take', 'page_size', 'per_page').
        offset_key: The key used to specify the starting position or number of items to skip (e.g., 'offset').
        cursor_key: The key used for cursor-based pagination to continue from a specific point (e.g., 'cursor', 'next_cursor', 'page_after').
    """

    page_number_key: str | None = None
    limit_key: str | None = None
    offset_key: str | None = None
    cursor_key: str | None = None


class ParameterDetectionResult(BaseModel):
    """
    Args:
        apply_parameters_code: Python function code that applies both pagination and dynamic parameters to a request.
        pagination_keys: Traditional pagination parameter names for PaginationStrategy integration.
        dynamic_parameter_keys: User-controllable business logic parameters (sorting, filtering, search, etc.).
    """

    apply_parameters_code: str
    pagination_keys: PaginationKeys
    dynamic_parameter_keys: list[str]
