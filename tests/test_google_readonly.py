import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from aic_connector.google_readonly import GoogleReadOnlyClient


class GoogleReadOnlyTests(unittest.TestCase):
    def test_token_required(self):
        with self.assertRaises(ValueError):
            GoogleReadOnlyClient("")

    def test_youtube_read_only_request(self):
        client = GoogleReadOnlyClient("test-token")
        client._get = AsyncMock(return_value={"items": []})
        result = asyncio.run(client.youtube_my_channel())
        self.assertEqual(result, {"items": []})
        args, kwargs = client._get.await_args
        self.assertIn("/youtube/v3/channels", args[0])
        self.assertEqual(args[1]["mine"], "true")

    def test_drive_metadata_request(self):
        client = GoogleReadOnlyClient("test-token")
        client._get = AsyncMock(return_value={"files": []})
        asyncio.run(client.drive_list_metadata(page_size=12))
        args, kwargs = client._get.await_args
        self.assertEqual(args[1]["page_size"], "12")
        self.assertIn("files(id,name,mimeType,modifiedTime)", args[1]["fields"])

    def test_invalid_page_size(self):
        with self.assertRaises(ValueError):
            asyncio.run(GoogleReadOnlyClient("test-token").drive_list_metadata(page_size=1000))


if __name__ == "__main__":
    unittest.main()
