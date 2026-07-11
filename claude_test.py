from anthropic import Anthropic
from config import config

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=50,
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly: Claude connection successful"
        }
    ]
)

print(response.content[0].text)
