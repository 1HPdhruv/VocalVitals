import os
from functools import lru_cache


def _read_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_audio_classifier():
    """Lazy-load HuggingFace AudioSet classifier once per process."""
    from transformers import pipeline

    model_name = os.getenv("AUDIO_CLASSIFIER_MODEL", "MIT/ast-finetuned-audioset")
    use_cpu = _read_bool("AUDIO_MODEL_CPU", default=True)
    device = -1 if use_cpu else 0

    return pipeline(
        "audio-classification",
        model=model_name,
        device=device,
    )


def classify_audio_file(audio_path: str, top_k: int = 15):
    classifier = get_audio_classifier()
    results = classifier(audio_path, top_k=top_k)
    if isinstance(results, dict):
        return [results]
    return results
