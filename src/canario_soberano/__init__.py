"""Canário Soberano X: núcleo multimodal CPU-first e explicável."""

from .engine import CanarioEngine, EngineResult
from .schemas import Modality, MultimodalRequest, RequestValidationError

__all__ = [
    "CanarioEngine",
    "EngineResult",
    "Modality",
    "MultimodalRequest",
    "RequestValidationError",
]
