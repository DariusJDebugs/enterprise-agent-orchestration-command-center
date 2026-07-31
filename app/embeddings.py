from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}")


class HashEmbeddingModel:
    """Deterministic local embedding model for an offline, reproducible MVP.

    It uses feature hashing with signed buckets and L2 normalization. The vector
    store remains provider-neutral: this model can later be replaced by a hosted
    or local neural embedding model without changing the repository API.
    """

    def __init__(self, dimensions: int = 192):
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        tokens = [token.lower() for token in TOKEN_RE.findall(text)]
        counts = Counter(tokens)
        vector = [0.0] * self.dimensions
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + math.log(count)
            vector[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            raise ValueError("vectors must have equal dimensions")
        return sum(a * b for a, b in zip(left, right, strict=True))
