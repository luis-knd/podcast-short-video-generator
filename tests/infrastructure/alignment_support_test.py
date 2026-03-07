def build_fake_alignment_payload() -> dict[str, object]:
    return {
        "metadata": {"aligner": "fake"},
        "words": [
            {
                "text": "Hello",
                "normalized_text": "hello",
                "start_ms": 100,
                "end_ms": 300,
                "confidence": 0.9,
            },
            {
                "text": "world",
                "normalized_text": "world",
                "start_ms": 320,
                "end_ms": 600,
                "confidence": 0.8,
            },
        ],
    }
