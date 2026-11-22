import pytest

from canario_soberano import (
    CanarioEngine,
    Modality,
    MultimodalRequest,
    RequestValidationError,
)


def test_text_request_is_validated_without_claiming_inference():
    request = MultimodalRequest.from_dict({
        "request_id": "test-1",
        "items": [{"modality": "text", "content": "Olá, Canário"}],
    })
    result = CanarioEngine().process(request).to_dict()
    assert result["status"] == "accepted_with_unprocessed_modalities"
    assert result["results"][0]["status"] == "validated_not_inferred"
    assert result["audit"]["input_manifest_sha256"]


def test_mixed_modalities_are_routed_without_downloading_media():
    request = MultimodalRequest.from_dict({
        "items": [
            {"modality": "text", "content": "Analisar contexto"},
            {"modality": "image", "uri": "https://example.org/frame.jpg",
             "mime_type": "image/jpeg"},
            {"modality": "audio", "uri": "file:///tmp/sample.wav",
             "mime_type": "audio/wav"},
        ]
    })
    result = CanarioEngine().process(request)
    assert set(result.accepted_modalities) == {"text", "image", "audio"}
    assert result.audit["model_calls"] == 0


def test_rejects_unsupported_uri_scheme():
    with pytest.raises(RequestValidationError):
        MultimodalRequest.from_dict({
            "items": [{"modality": "image", "uri": "http://example.org/a.jpg"}]
        })


def test_rejects_empty_request():
    with pytest.raises(RequestValidationError):
        MultimodalRequest.from_dict({"items": []})


def test_video_modality_is_supported_as_reference():
    request = MultimodalRequest.from_dict({
        "items": [{"modality": "video", "uri": "https://example.org/clip.mp4",
                   "mime_type": "video/mp4"}]
    })
    assert request.items[0].modality is Modality.VIDEO



def test_text_content_changes_audit_manifest_hash():
    first = MultimodalRequest.from_dict({
        "items": [{"modality": "text", "content": "primeiro"}]
    })
    second = MultimodalRequest.from_dict({
        "items": [{"modality": "text", "content": "segundo"}]
    })
    first_hash = CanarioEngine().process(first).audit["input_manifest_sha256"]
    second_hash = CanarioEngine().process(second).audit["input_manifest_sha256"]
    assert first_hash != second_hash


def test_rejects_mime_type_from_another_modality():
    with pytest.raises(RequestValidationError):
        MultimodalRequest.from_dict({
            "items": [{"modality": "audio", "uri": "https://example.org/a.wav",
                       "mime_type": "image/png"}]
        })
