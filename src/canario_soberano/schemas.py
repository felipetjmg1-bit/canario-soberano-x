"""Contratos de entrada multimodal. Nenhum conteúdo externo é baixado automaticamente."""

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse


class RequestValidationError(ValueError):
    """Entrada inválida ou acima dos limites locais."""


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True)
class ModalityItem:
    modality: Modality
    content: str | None = None
    uri: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, max_text_chars: int = 20_000) -> None:
        if self.modality is Modality.TEXT:
            if not isinstance(self.content, str) or not self.content.strip():
                raise RequestValidationError("Itens de texto precisam de conteúdo não vazio.")
            if len(self.content) > max_text_chars:
                raise RequestValidationError("Texto excede o limite configurado.")
            if self.uri:
                raise RequestValidationError("Itens de texto não aceitam URI.")
            return
        if self.content:
            raise RequestValidationError(
                "Mídias devem ser referenciadas por URI; bytes não são aceitos neste núcleo."
            )
        if self.mime_type:
            expected = {
                Modality.IMAGE: "image/",
                Modality.AUDIO: "audio/",
                Modality.VIDEO: "video/",
            }[self.modality]
            if not self.mime_type.startswith(expected):
                raise RequestValidationError("MIME type incompatível com a modalidade.")
        if not self.uri:
            raise RequestValidationError("Itens de mídia precisam de URI.")
        parsed = urlparse(self.uri)
        if parsed.scheme not in {"https", "file"}:
            raise RequestValidationError("URI de mídia deve usar HTTPS ou file:// local.")
        if parsed.scheme == "https" and not parsed.netloc:
            raise RequestValidationError("URI HTTPS inválida.")
        if self.mime_type and not self.mime_type.startswith(
            ("image/", "audio/", "video/")
        ):
            raise RequestValidationError("MIME type incompatível com mídia.")

    def public_metadata(self) -> dict[str, Any]:
        metadata = {
            "modality": self.modality.value,
            "mime_type": self.mime_type,
            "uri_present": bool(self.uri),
            "metadata_keys": sorted(self.metadata.keys()),
        }
        if self.modality is Modality.TEXT and isinstance(self.content, str):
            metadata["content_sha256"] = sha256(self.content.encode("utf-8")).hexdigest()
        return metadata


@dataclass(frozen=True)
class MultimodalRequest:
    items: tuple[ModalityItem, ...]
    request_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MultimodalRequest":
        if not isinstance(payload, dict):
            raise RequestValidationError("A requisição deve ser um objeto.")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise RequestValidationError("Informe ao menos um item em 'items'.")
        if len(raw_items) > 16:
            raise RequestValidationError("Limite de 16 itens por requisição.")
        items = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise RequestValidationError("Cada item deve ser um objeto.")
            try:
                modality = Modality(raw.get("modality"))
            except (ValueError, TypeError) as exc:
                raise RequestValidationError("Modalidade não suportada.") from exc
            item = ModalityItem(
                modality=modality,
                content=raw.get("content"),
                uri=raw.get("uri"),
                mime_type=raw.get("mime_type"),
                metadata=raw.get("metadata") or {},
            )
            if not isinstance(item.metadata, dict):
                raise RequestValidationError("metadata deve ser um objeto.")
            item.validate()
            items.append(item)
        context = payload.get("context") or {}
        if not isinstance(context, dict):
            raise RequestValidationError("context deve ser um objeto.")
        return cls(tuple(items), payload.get("request_id"), context)
