"""Translation helper utilities.

Supports multiple providers via environment variables. If no provider or API key
is supplied the functions will return an empty string (no automatic translation).

Environment variables used:
- TRANSLATOR_PROVIDER: 'google' or 'azure'
- GOOGLE_TRANSLATE_API_KEY: API key for Google Cloud Translate v2
- AZURE_TRANSLATOR_KEY: subscription key for Azure Translator
- AZURE_TRANSLATOR_ENDPOINT: endpoint URL (e.g. https://api.cognitive.microsofttranslator.com)
- AZURE_TRANSLATOR_REGION: (optional) region header for Azure

This file intentionally does not make network calls unless credentials are set.
"""
from __future__ import annotations
import os
import json
from typing import Optional

try:
    import requests
except Exception:
    requests = None


def translate_text(text: str, target_lang: str = 'ta') -> str:
    """Translate text to the target language using configured provider.

    Returns translated text on success, or empty string on failure / misconfiguration.
    """
    if not text:
        return ''

    provider = os.environ.get('TRANSLATOR_PROVIDER', '').strip().lower()
    if not provider:
        return ''

    if requests is None:
        # requests not installed; cannot perform network translations
        return ''

    try:
        if provider == 'google':
            api_key = os.environ.get('GOOGLE_TRANSLATE_API_KEY')
            if not api_key:
                return ''
            url = 'https://translation.googleapis.com/language/translate/v2'
            payload = {
                'q': text,
                'target': target_lang,
                'format': 'text',
                'key': api_key,
            }
            resp = requests.post(url, data=payload, timeout=10)
            if resp.status_code != 200:
                return ''
            data = resp.json()
            return data.get('data', {}).get('translations', [{}])[0].get('translatedText', '')

        if provider == 'azure':
            key = os.environ.get('AZURE_TRANSLATOR_KEY')
            endpoint = os.environ.get('AZURE_TRANSLATOR_ENDPOINT')
            if not key or not endpoint:
                return ''
            region = os.environ.get('AZURE_TRANSLATOR_REGION', '')
            url = f"{endpoint.rstrip('/')}/translate?api-version=3.0&to={target_lang}"
            headers = {
                'Ocp-Apim-Subscription-Key': key,
                'Content-Type': 'application/json',
            }
            if region:
                headers['Ocp-Apim-Subscription-Region'] = region
            body = [{ 'Text': text }]
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            if resp.status_code != 200:
                return ''
            data = resp.json()
            # Azure returns a list of translations per input
            try:
                return data[0]['translations'][0]['text']
            except Exception:
                return ''

    except Exception:
        return ''

    return ''
