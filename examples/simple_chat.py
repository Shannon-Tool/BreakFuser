"""Run a minimal chat request using the configured provider model aliases."""

from BreakFuser import BreakFuser

client = BreakFuser()
response = client.chat.completions.create(messages=[{"role": "user", "content": "Hello!"}])
print(response.choices[0].message.content)
client.close()
