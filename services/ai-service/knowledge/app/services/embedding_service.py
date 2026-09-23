"""
Embedding service.

The preferred backend runs BGE-M3 through sentence-transformers, giving real
semantic vectors. That needs torch, a multi-gigabyte install, so ``auto`` falls
back to a deterministic hashed bag-of-words embedding whenever torch or the
model is unavailable. The fallback is lexical rather than semantic, but it
keeps the whole ingest pipeline and keyword retrieval working with nothing
extra to download.

Both backends return ``settings.embedding_dimension`` L2-normalised floats, so
the stored vectors stay comparable and the Postgres dot-product search only
ever needs to compare vectors of the same length. The hashing backend is pure
standard library, so it needs no numpy.
"""

import hashlib
import importlib.util
import math
import re
from typing import TYPE_CHECKING

from structlog import get_logger

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)
settings = get_settings()

_model: "SentenceTransformer | None" = None
_model_load_failed: bool = False

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HASH_SEED = "aifya-knowledge-v1"

_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def _sentence_transformers_importable() -> bool:
    """
    Whether sentence-transformers and torch are installed.

    @returns True when both packages can be imported
    """
    try:
        return (
            importlib.util.find_spec("sentence_transformers") is not None
            and importlib.util.find_spec("torch") is not None
        )
    except Exception:
        return False


def backend_name() -> str:
    """
    Name of the backend that will be used, without loading any model.
    Safe to call from health checks and request logging.

    @returns Either 'sentence-transformers' or 'hashing'
    """
    requested = settings.embedding_backend
    if requested == "hashing":
        return "hashing"
    if requested == "sentence-transformers":
        return "sentence-transformers"
    return (
        "sentence-transformers"
        if _sentence_transformers_importable()
        else "hashing"
    )


def _load_model() -> "SentenceTransformer | None":
    """
    Load and cache the sentence-transformers model.

    Records a permanent failure after the first error so a missing model or a
    failed download is not retried on every chunk.

    @returns The loaded model, or None when it cannot be loaded
    """
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return _model
    if not _sentence_transformers_importable():
        _model_load_failed = True
        return None

    try:
        from sentence_transformers import SentenceTransformer

        logger.info("embedding_model_loading", model=settings.embedding_model)
        _model = SentenceTransformer(
            settings.embedding_model,
            trust_remote_code=True,
        )
        logger.info(
            "embedding_model_loaded",
            model=settings.embedding_model,
            dimension=_model.get_sentence_embedding_dimension(),
        )
    except Exception as exc:
        logger.warning(
            "embedding_model_unavailable",
            model=settings.embedding_model,
            error=str(exc),
            fallback="hashing",
        )
        _model = None
        _model_load_failed = True
    return _model


def active_backend() -> str:
    """
    Resolve the backend for this process, loading the model if needed.

    @returns Either 'sentence-transformers' or 'hashing'
    """
    if settings.embedding_backend == "hashing":
        return "hashing"
    return "sentence-transformers" if _load_model() is not None else "hashing"


def _features(text: str) -> list[str]:
    """
    Tokenise a string into the unigram and bigram features we hash.

    @param text: Raw text
    @returns Feature strings
    """
    tokens = _TOKEN_RE.findall(text.lower())
    features = list(tokens)
    features.extend(
        f"{first}_{second}" for first, second in zip(tokens, tokens[1:])
    )
    return features


def _hashed_vector(text: str) -> list[float]:
    """
    Deterministic hashed bag-of-words embedding.

    Each feature is hashed into one of ``embedding_dimension`` buckets with a
    signed weight and sub-linear term frequency, then the vector is L2
    normalised so a dot product behaves like normalised lexical overlap.

    @param text: Raw text to embed
    @returns L2-normalised vector of length embedding_dimension
    """
    dim = settings.embedding_dimension
    vector = [0.0] * dim

    counts: dict[str, int] = {}
    for feature in _features(text):
        counts[feature] = counts.get(feature, 0) + 1

    for feature, count in counts.items():
        digest = hashlib.blake2b(
            f"{_HASH_SEED}:{feature}".encode("utf-8"), digest_size=8
        ).digest()
        value = int.from_bytes(digest, "big")
        sign = 1.0 if value & 1 else -1.0
        vector[value % dim] += sign * (1.0 + math.log(count))

    norm = math.sqrt(sum(component * component for component in vector))
    if norm > 0.0:
        vector = [component / norm for component in vector]
    return vector


def _to_lists(embeddings: object) -> list[list[float]]:
    """
    Normalise a sentence-transformers result into plain lists.

    @param embeddings: Array-like of vectors (numpy array or list)
    @returns List of float lists
    """
    if hasattr(embeddings, "tolist"):
        converted = embeddings.tolist()  # type: ignore[attr-defined]
        return [list(vector) for vector in converted]
    return [list(vector) for vector in embeddings]  # type: ignore[union-attr]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    @param texts: List of text strings to embed
    @returns List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    if active_backend() == "hashing" or _model is None:
        return [_hashed_vector(text) for text in texts]

    batch_size = settings.embedding_batch_size
    all_embeddings: list[list[float]] = []
    for index in range(0, len(texts), batch_size):
        batch = texts[index : index + batch_size]
        vectors = _to_lists(
            _model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        )
        all_embeddings.extend(vectors)
        logger.debug(
            "embedding_batch_complete",
            batch_start=index,
            batch_size=len(batch),
        )

    return all_embeddings


def embed_query(query: str) -> list[float]:
    """
    Generate the embedding for a single search query.

    @param query: Query text
    @returns Embedding vector
    """
    if active_backend() == "hashing" or _model is None:
        return _hashed_vector(query)

    vectors = _to_lists(
        _model.encode(
            _QUERY_INSTRUCTION + query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    )
    return vectors[0]