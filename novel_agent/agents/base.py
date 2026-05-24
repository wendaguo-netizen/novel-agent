from openai import OpenAI
from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL


class BaseAgent:
    def __init__(self, model: str = MODEL):
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = model

    def call_with_context(self, system: str, user_content: str, max_tokens: int = 4096) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content or ""

    def stream_write_gen(self, system: str, user_content: str, max_tokens: int = 8192):
        """Generator: yields text chunks as they arrive."""
        stream = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def stream_write(self, system: str, user_content: str, max_tokens: int = 8192) -> str:
        """CLI version: prints chunks and returns full text."""
        result = []
        for chunk in self.stream_write_gen(system, user_content, max_tokens):
            result.append(chunk)
            print(chunk, end="", flush=True)
        print()
        return "".join(result)
