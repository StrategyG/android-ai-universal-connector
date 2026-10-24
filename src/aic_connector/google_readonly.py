"""Read-only Google API client; bearer tokens must come from trusted backend storage.

This module does not manage login or store credentials. It cannot publish,
delete, upload, or mutate Google resources.
"""
from __future__ import annotations

from typing import Any

import httpx2


class GoogleReadOnlyClient:
    def __init__(self, access_token: str, *, timeout: float = 10.0):
        if not access_token:
            raise ValueError("verified_google_access_token_required")
        if not 0 < timeout <= 60:
            raise ValueError("timeout_out_of_range")
        self._token = access_token
        self._timeout = timeout

    async def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        async with httpx2.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict):
            raise ValueError("google_api_response_invalid")
        return result

    async def youtube_my_channel(self) -> dict[str, Any]:
        """Requires youtube.readonly; caller must authorize scope before invocation."""
        return await self._get(
            "https://www.googleapis.com/youtube/v3/channels",
            {"part": "snippet,statistics", "mine": "true"},
        )

    async def drive_list_metadata(self, *, page_size: int = 25) -> dict[str, Any]:
        """Requires drive.metadata.readonly; never fetches file content."""
        if not 1 <= page_size <= 100:
            raise ValueError("page_size_out_of_range")
        return await self._get(
            "https://www.googleapis.com/drive/v3/files",
            {"page_size": str(page_size), "fields": "nextPageToken,files(id,name,mimeType,modifiedTime)", "spaces": "drive"},
        )
