import re

def calculate_stylometric_score(text: str) -> float:
    """
    Analyzes statistical properties of text and returns a score between 0 and 1.
    1.0 = very likely AI generated
    0.0 = very likely human written
    """
    sentences = _get_sentences(text)
    words = _get_words(text)

    if len(sentences) < 2 or len(words) < 10:
        return 0.5

    # Metric 1: Sentence length variance
    sentence_lengths = [len(s.split()) for s in sentences]
    avg_length = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)
    std_dev = variance ** 0.5
    variance_score = max(0.0, 1.0 - (std_dev / 8.0))

    # Metric 2: Type-token ratio
    unique_words = set(w.lower() for w in words)
    ttr = len(unique_words) / len(words)
    ttr_score = max(0.0, 1.0 - (ttr / 0.6))

    # Metric 3: Informal punctuation
    informal_punct = len(re.findall(r'[!?]|\.{2,}|\-\-', text))
    informal_score = max(0.0, 1.0 - (informal_punct / max(len(sentences), 1)))

    # Metric 4: Average sentence length
    length_score = min(avg_length / 20.0, 1.0)

    # Weighted combination
    final_score = (
        variance_score * 0.3 +
        ttr_score * 0.3 +
        informal_score * 0.2 +
        length_score * 0.2
    )

    return round(min(max(final_score, 0.0), 1.0), 3)

def _get_sentences(text: str):
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]

def _get_words(text: str):
    return re.findall(r'\b\w+\b', text)