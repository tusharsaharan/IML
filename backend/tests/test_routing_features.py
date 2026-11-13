"""Feature extraction tests. Labels elsewhere are authored fixtures, not model correctness."""
from __future__ import annotations

import math

from gateway.features.routing.features import MODEL_FEATURE_NAMES, extract_features


def test_empty_and_whitespace_only_are_safe():
    for text in ("", "   \n\t "):
        features = extract_features(text)
        assert features.language_group == "unknown"
        assert len(features.vector()) == len(MODEL_FEATURE_NAMES)
        assert all(math.isfinite(value) for value in features.vector())


def test_plain_english_sentence():
    features = extract_features("Hello")
    assert features.language_group == "english"
    assert features.code_mix_ratio == 0


def test_romanized_hinglish_sentence():
    # The imported helper really returns "hinglish" for this input.
    assert extract_features("bhai kal chutti hai kya").language_group == "hinglish"


def test_devanagari_sentence_is_hindi():
    features = extract_features("मेरे खाते का पैसा नहीं भेजना")
    assert features.language_group == "hindi"
    assert features.devanagari_ratio > 0.9


def test_mixed_devanagari_and_latin_has_code_mix():
    assert extract_features("मेरा wifi काम नहीं कर रहा").code_mix_ratio > 0


def test_email_counts_as_one_word_and_sets_flag():
    features = extract_features("user@example.com")
    assert features.word_count == 1
    assert features.has_email_or_amount == 1


def test_vector_shape_determinism_and_finiteness():
    text = "yaar mera email user@example.com par bhejo na, deadline kal hai"
    first = extract_features(text)
    second = extract_features(text)
    assert len(first.vector()) == len(MODEL_FEATURE_NAMES)
    assert first.vector() == second.vector()
    assert first.as_dict() == second.as_dict()
    assert all(isinstance(value, float) for value in first.vector())
    assert all(math.isfinite(value) for value in first.vector())


def test_long_input_is_truncated_without_raising():
    features = extract_features("a " * 15_000)  # 30,000 characters
    assert features.truncated is True
    assert features.char_length == 30_000
    assert len(features.vector()) == len(MODEL_FEATURE_NAMES)
