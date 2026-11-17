"""
The ONLY module that talks to the LLM provider.

Swapping providers means changing this file. Tests replace the client with a
fake. The API key is read from settings (which read .env) and is only ever
sent from the server, never to the browser.

It speaks the "OpenAI-style" chat completions shape (POST <base URL>/chat/completions
with a Bearer key). Google serves that shape for Gemini at
https://generativelanguage.googleapis.com/v1beta/openai/, so the provider is
chosen by AI_API_BASE_URL and AI_API_MODEL in .env.

UNVERIFIED: not yet run against the live service from this project.
"""

import json
import logging

import requests
from django.conf import settings


logger = logging.getLogger('ai')


class AIError(Exception):
    """The model call failed or returned something unusable. The text is safe to show to a user."""


class GeminiClient:
    def __init__(self, api_key, model, base_url, timeout=15):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def generate_json(self, prompt):
        """Send a prompt, return the parsed JSON object the model produced."""
        try:
            response = requests.post(
                f'{self.base_url.rstrip("/")}/chat/completions',
                headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': self.model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'response_format': {'type': 'json_object'},
                    'temperature': 0.4,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = response.json()['choices'][0]['message']['content']
            data = json.loads(text)
        except requests.RequestException as exc:
            status = getattr(exc.response, 'status_code', None)
            logger.warning('AI call failed: %s, HTTP status %s', type(exc).__name__, status)
            if status == 429:
                raise AIError('The AI is busy right now.') from exc
            if isinstance(exc, requests.Timeout):
                raise AIError('The AI took too long to answer.') from exc
            raise AIError('The AI is not available right now.') from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning('AI call failed: unexpected response (%s)', type(exc).__name__)
            raise AIError('The AI gave an answer the app could not use.') from exc
        if not isinstance(data, dict):
            logger.warning('AI call failed: unexpected response (not a JSON object)')
            raise AIError('The AI gave an answer the app could not use.')
        return data


def default_client():
    """A real client if a key is configured, otherwise None (the app uses its fallback)."""
    if not settings.AI_API_KEY:
        return None
    return GeminiClient(settings.AI_API_KEY, settings.AI_API_MODEL, settings.AI_API_BASE_URL,
                        settings.AI_TIMEOUT_SECONDS)
