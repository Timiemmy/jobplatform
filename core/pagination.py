"""
core/pagination.py

Mandatory pagination enforced across all list endpoints.
Every list response MUST conform to:

{
    "count": int,
    "next": string | null,
    "previous": string | null,
    "results": [...]
}
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPageNumberPagination(PageNumberPagination):
    """
    Default paginator for all list views.

    Clients control page size via ?page_size= up to MAX_PAGE_SIZE.
    ?page= controls which page is returned.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data: list) -> Response:
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema: dict) -> dict:
        """For drf-spectacular schema generation."""
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "count": {"type": "integer", "example": 42},
                "next": {"type": "string", "nullable": True, "format": "uri"},
                "previous": {"type": "string", "nullable": True, "format": "uri"},
                "results": schema,
            },
        }
