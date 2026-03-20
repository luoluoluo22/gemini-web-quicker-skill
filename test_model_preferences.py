import unittest
from unittest import mock

from libs.api_client import AntigravityClient


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


class GeminiModelPreferenceTests(unittest.TestCase):
    def make_client(self, config=None):
        client = AntigravityClient.__new__(AntigravityClient)
        client.config = config or {}
        client.base_url = "http://127.0.0.1:55557/v1"
        client.api_key = "test-key"
        return client

    def test_chat_completion_prefers_gemini_3_1_pro_by_default(self):
        client = self.make_client()

        with mock.patch("libs.api_client.s.post") as mock_post:
            mock_post.return_value = DummyResponse(status_code=200)

            client.chat_completion([{"role": "user", "content": "hi"}])

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gemini-3.1-pro-preview")

    def test_generate_image_prefers_gemini_3_1_flash_image_by_default(self):
        client = self.make_client()

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.headers.get.return_value = "application/json"
            response.read.return_value = b'{"choices":[{"message":{"content":"ok"}}]}'
            mock_urlopen.return_value = response

            client.generate_image("test prompt")

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.data.decode("utf-8").find('"model": "gemini-3.1-flash-image-preview"') >= 0, True)

    def test_get_models_adds_preferred_gemini_3_1_models_when_endpoint_is_stale(self):
        client = self.make_client()

        remote_models = {
            "data": [
                {"id": "gemini-3-flash"},
                {"id": "gemini-3-pro"},
                {"id": "gemini-3-pro-image"},
            ]
        }

        with mock.patch("libs.api_client.s.get") as mock_get:
            mock_get.return_value = DummyResponse(status_code=200, json_data=remote_models)

            models = client.get_models()

        model_ids = [item["id"] if isinstance(item, dict) else item for item in models]
        self.assertIn("gemini-3.1-pro-preview", model_ids)
        self.assertIn("gemini-3.1-flash-lite-preview", model_ids)
        self.assertIn("gemini-3.1-flash-image-preview", model_ids)

    def test_get_models_prioritizes_preferred_gemini_3_1_models_in_display_order(self):
        client = self.make_client()

        remote_models = {
            "data": [
                {"id": "gemini-3-flash"},
                {"id": "gemini-3-pro"},
            ]
        }

        with mock.patch("libs.api_client.s.get") as mock_get:
            mock_get.return_value = DummyResponse(status_code=200, json_data=remote_models)

            models = client.get_models()

        model_ids = [item["id"] if isinstance(item, dict) else item for item in models]
        self.assertEqual(model_ids[0], "gemini-3.1-pro-preview")


if __name__ == "__main__":
    unittest.main()
