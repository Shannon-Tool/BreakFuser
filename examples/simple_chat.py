from BreakFuser import BreakFuser

client = BreakFuser(
    decider="typesafe/jev-1.14",
    uncensoredmodel="huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF",
    smartmodel="anthropic/claude-opus-5",
)
response = client.chat.completions.create(messages=[{"role": "user", "content": "Hello!"}])
print(response.choices[0].message.content)
client.close()
