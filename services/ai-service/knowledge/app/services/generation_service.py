"""
Generation service using vLLM-hosted LLMs.
Generates answers from retrieved document chunks with citations.
"""

import httpx
from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


_SYSTEM_PROMPT_EN = """You are an institutional knowledge assistant for a hospital using the Aifya Health Platform.
Your role is to answer questions based ONLY on the provided document excerpts.

Rules:
1. Answer ONLY from the provided context. Do not use external knowledge.
2. If the context does not contain enough information, say so clearly.
3. Cite your sources using [Source N] notation, where N corresponds to the excerpt number.
4. Be precise and clinical in your language.
5. If a policy has an effective date, mention it.
6. For medication or clinical guidelines, include relevant warnings or contraindications from the source.
7. Keep answers concise but complete."""

_SYSTEM_PROMPT_SW = """Wewe ni msaidizi wa maarifa ya taasisi kwa hospitali inayotumia Jukwaa la Afya la Aifya.
Jukumu lako ni kujibu maswali kulingana TU na dondoo za hati zilizotolewa.

Kanuni:
1. Jibu TU kutoka kwa muktadha uliotolewa. Usitumie maarifa ya nje.
2. Ikiwa muktadha hauna habari za kutosha, sema hivyo wazi.
3. Taja vyanzo vyako kwa kutumia alama ya [Chanzo N], ambapo N inalingana na nambari ya dondoo.
4. Kuwa sahihi na wa kitabibu katika lugha yako.
5. Ikiwa sera ina tarehe ya kuanza kutumika, itaje.
6. Kwa miongozo ya dawa au kliniki, jumuisha onyo au vikwazo husika kutoka kwa chanzo.
7. Weka majibu mafupi lakini kamili."""


def _build_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into numbered context for the LLM.

    @param chunks: List of retrieval result dicts with text, document_title, section_title, page_number
    @returns Formatted context string
    """
    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        header_parts = [f"[Source {i}]"]
        title = chunk.get("document_title", "Unknown Document")
        header_parts.append(f"Document: {title}")

        section = chunk.get("section_title")
        if section:
            header_parts.append(f"Section: {section}")

        page = chunk.get("page_number")
        if page:
            header_parts.append(f"Page: {page}")

        header = " | ".join(header_parts)
        text = chunk.get("text", "")
        parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(parts)


def _auth_headers() -> dict[str, str]:
    """
    Authorization header for the OpenAI-compatible generation endpoint.

    @returns Headers dict, empty when no API key is configured
    """
    if settings.generation_api_key:
        return {"Authorization": f"Bearer {settings.generation_api_key}"}
    return {}


async def generate_answer(
    query: str,
    chunks: list[dict],
    language: str = "en",
) -> dict:
    """
    Generate an answer using the vLLM-hosted model with retrieved context.

    @param query: User's question
    @param chunks: Retrieved document chunks
    @param language: Response language ('en' or 'sw')
    @returns Dict with 'answer', 'model_used', 'confidence'
    """
    if not chunks:
        no_result = (
            "I could not find any relevant information in the institutional knowledge base for your query."
            if language == "en"
            else "Sikupata habari yoyote inayohusiana katika hifadhi ya maarifa ya taasisi kwa swali lako."
        )
        return {
            "answer": no_result,
            "model_used": settings.generation_model,
            "confidence": 0.0,
        }

    context = _build_context(chunks)
    system_prompt = _SYSTEM_PROMPT_EN if language == "en" else _SYSTEM_PROMPT_SW

    user_message = f"""Based on the following institutional documents, answer the question.

## Documents

{context}

## Question

{query}

## Instructions
Provide a clear, well-structured answer. Cite sources using [Source N] notation. If the documents don't fully answer the question, state what information is available and what is missing."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.vllm_base_url}/chat/completions",
                headers=_auth_headers(),
                json={
                    "model": settings.generation_model,
                    "messages": messages,
                    "max_tokens": settings.generation_max_tokens,
                    "temperature": settings.generation_temperature,
                    "top_p": 0.9,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        answer_text = data["choices"][0]["message"]["content"]

        avg_score = sum(c.get("score", 0.5) for c in chunks) / len(chunks)
        confidence = min(1.0, avg_score * 1.1)

        logger.info(
            "answer_generated",
            query_length=len(query),
            context_chunks=len(chunks),
            answer_length=len(answer_text),
            confidence=round(confidence, 3),
        )

        return {
            "answer": answer_text,
            "model_used": settings.generation_model,
            "confidence": round(confidence, 3),
        }

    except httpx.HTTPError as exc:
        logger.error("vllm_generation_error", error=str(exc))
        fallback = (
            "I was unable to generate an answer due to a service error. "
            "The relevant document excerpts are shown in the citations below."
            if language == "en"
            else "Sikuweza kutoa jibu kutokana na hitilafu ya huduma. "
            "Dondoo husika za hati zinaonyeshwa katika vyanzo hapa chini."
        )
        return {
            "answer": fallback,
            "model_used": settings.generation_model,
            "confidence": 0.0,
        }


async def check_health() -> str:
    """
    Check vLLM connectivity.

    @returns Status string: 'connected' or 'disconnected'
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.vllm_base_url}/models",
                headers=_auth_headers(),
            )
            if resp.status_code == 200:
                return "connected"
            return "degraded"
    except Exception:
        return "disconnected"
