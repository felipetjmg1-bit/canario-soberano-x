"""Orquestração multimodal determinística, sem alegar inferência sem modelo."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Protocol
from uuid import uuid4

from .schemas import Modality, MultimodalRequest


@dataclass(frozen=True)
class AdapterResult:
    output: Any
    explanation: str
    model_name: str
    model_version: str


class ModalityAdapter(Protocol):
    def supports(self, modality: Modality) -> bool: ...
    def process(self, item: Any) -> AdapterResult: ...


@dataclass(frozen=True)
class EngineResult:
    request_id: str
    status: str
    accepted_modalities: list[str]
    results: list[dict[str, Any]]
    explanation: dict[str, Any]
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CanarioEngine:
    """Valida entradas, seleciona adaptadores explícitos e gera trilha XAI auditável."""

    def __init__(self, adapters: list[ModalityAdapter] | None = None) -> None:
        self.adapters = adapters or []

    def process(self, request: MultimodalRequest) -> EngineResult:
        request_id = request.request_id or str(uuid4())
        results: list[dict[str, Any]] = []
        explanations: list[str] = []
        for item in request.items:
            adapter = next((a for a in self.adapters if a.supports(item.modality)), None)
            if adapter is None:
                results.append({
                    "modality": item.modality.value,
                    "status": "validated_not_inferred",
                    "metadata": item.public_metadata(),
                })
                explanations.append(
                    f"{item.modality.value}: entrada validada; nenhum adaptador de inferência foi configurado."
                )
                continue
            result = adapter.process(item)
            results.append({
                "modality": item.modality.value,
                "status": "processed_by_adapter",
                "output": result.output,
                "adapter": result.model_name,
                "adapter_version": result.model_version,
            })
            explanations.append(result.explanation)

        canonical = json.dumps(
            {"request_id": request_id, "items": [i.public_metadata() for i in request.items]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = sha256(canonical).hexdigest()
        return EngineResult(
            request_id=request_id,
            status="completed" if all(r["status"] == "processed_by_adapter" for r in results)
            else "accepted_with_unprocessed_modalities",
            accepted_modalities=sorted({i.modality.value for i in request.items}),
            results=results,
            explanation={
                "method": "explicit_adapter_routing",
                "statements": explanations,
                "confidence": None,
                "limitations": [
                    "Sem adaptador, não há inferência sobre o conteúdo da mídia.",
                    "URIs não são baixadas nem executadas automaticamente.",
                    "Explicações descrevem o fluxo; não provam correção sem avaliação externa.",
                ],
            },
            audit={
                "schema_version": "1.0",
                "input_manifest_sha256": digest,
                "item_count": len(request.items),
                "model_calls": sum(r["status"] == "processed_by_adapter" for r in results),
            },
        )
