import os
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_SYSTEM_PROMPT = """You are a precise AI research assistant. Your task is to answer questions \
based ONLY on the document excerpts provided below.

Guidelines:
- Answer using only information present in the provided context.
- If the answer cannot be found, respond: "I couldn't find this information in the document."
- Be concise but thorough.
- Use bullet points or numbered lists when listing multiple items.
- Quote short relevant passages when they directly address the question."""


def generate_answer(question: str, context_chunks: List[str]) -> str:
    """Call the OpenAI Chat API to answer a question given retrieved context."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )

    client = OpenAI(api_key=api_key)

    context = "\n\n---\n\n".join(
        f"[Excerpt {i + 1}]:\n{chunk}" for i, chunk in enumerate(context_chunks)
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Document Context:\n{context}\n\nQuestion: {question}",
            },
        ],
        temperature=0.1,
        max_tokens=1500,
    )

    return response.choices[0].message.content
