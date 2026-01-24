# Centralized Hoax and Disinformation Patterns
HOAX_PATTERNS = [
    "alien", "ufo", "extraterrestrial", "et contact",
    "illuminati", "secret society", "cabal", "shadow government",
    "conspiracy", "cover-up", "leaked", "classified", "top secret",
    "ancient aliens", "alien alliance", "alien summit", "alien treaty",
    "reptilian", "annunaki", "grey aliens", "area 51",
    "new world order", "nwo", "global elite", "deep state",
    "flat earth", "earth is flat", "qanon", "pizzagate", "chemtrails",
    "fake proof", "hidden truth", "they don't want you to know", "world lie",
    "moon landing fake", "nasa lie"
]

REFUTATION_KEYWORDS = [
    "false", "debunked", "fake", "hoax", "myth", "not true", "fabricated",
    "disproven", "misleading", "pseudo", "incorrect", "erroneous", "untrue",
    "conspiracy theory", "misinformation", "disinformation", "manipulated",
    "synthetic", "ai generated", "deepfake", "cgi", "edited"
]

SUPPORT_KEYWORDS = [
    "true", "verified", "confirmed", "accurate", "factual", "correct",
    "reality", "official report", "verified by", "consensus", "proven"
]

# Analysis Thresholds
CONFIDENCE_THRESHOLD_STRICT = 0.85
CONFIDENCE_THRESHOLD_MODERATE = 0.70
VISUAL_RISK_THRESHOLD = 0.35
