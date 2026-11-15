"""
The ONLY module that talks to the LLM provider.

Swapping providers means changing this file. Tests replace the client with a
fake. The API key is read from settings (which read .env) and is only ever
sent from the server, never to the browser.

UNVERIFIED: the request shape below follows Google's Gemini REST API as I know
it. It has not been run against the live service from this project. Test it
with a real key before relying on it.
"""

import json

import requests
from django.conf import settings


class AIError(Exception):
    """The model call failed or returned something unusable."""


class GeminiClient:
    base_url = 'https://generativelanguage.googleapis.com/v1beta/models'

    def __init__(self, api_key, model, timeout=15):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate_json(self, prompt):
        """Send a prompt, return the parsed JSON object the model produced."""
        try:
            response = requests.post(
                f'{self.base_url}/{self.model}:generateContent',
                headers={'x-goog-api-key': self.api_key, 'Content-Type': 'application/json'},
                json={
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.4},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            data = json.loads(text)
        except requests.RequestException as exc:
            raise AIError(f'The AI service could not be reached ({type(exc).__name__}).') from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIError('The AI service returned an unexpected response.') from exc
        if not isinstance(data, dict):
            raise AIError('The AI service did not return a JSON object.')
        return data


def default_client():
    """A real client if a key is configured, otherwise None (the app uses its fallback)."""
    if not settings.LLM_API_KEY:
        return None
    return GeminiClient(settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_TIMEOUT_SECONDS)
