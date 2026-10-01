"""Call a running BreakFuser server from an OpenAI-shaped HTTP harness."""

import os

import httpx

base_url = os.getenv("BREAKFUSER_API_BASE_URL", "http://127.0.0.1:8000/v1")
api_key = os.getenv("BREAKFUSER_SERVER_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
response = httpx.post(
    f"{base_url}/chat/completions",
    headers=headers,
    json={
        "model": "breakfuser",
        "messages": [{"role": "user", "content": "Hello from an external harness!"}],
        "harvest_provenance": True,
    },
    timeout=60,
)
response.raise_for_status()
completion = response.json()
print(completion["choices"][0]["message"]["content"])
print(completion["breakfuser"]["fusion"])
