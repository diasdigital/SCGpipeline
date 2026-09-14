"""
app/services/text_cleaning.py
==============================
Layer 1 mitigation: markdown stripper for SelfCheckNLI.

spaCy sentence splitter (called inside HallucinationEvaluator) is designed
for plain prose. Markdown formatting (bullets, numbering, headers, dividers,
bold/italic) causes sentences to split into meaningless fragments
(e.g., just "1." or "-"), which ruins the NLI scoring.

This function cleans the text BEFORE entering evaluator.evaluate(),
without changing the original text stored/displayed to the user.
"""

import re


def strip_markdown_for_nlp(text: str) -> str:
    if not text:
        return text

    # Code block & inline code
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)

    # Horizontal rule / divider
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)

    # Heading markers
    text = re.sub(r"^[ \t]*#{1,6}[ \t]+", "", text, flags=re.MULTILINE)

    # Bullet markers
    text = re.sub(r"^[ \t]*[-*+][ \t]+", "", text, flags=re.MULTILINE)

    # Numbering markers (1. / 1) )
    text = re.sub(r"^[ \t]*\d+[.)][ \t]+", "", text, flags=re.MULTILINE)

    # Bold / italic
    text = re.sub(r"\*{1,3}([^*\n]+?)\*{1,3}", r"\1", text)
    text = re.sub(r"(?<!\w)_{1,2}([^_\n]+?)_{1,2}(?!\w)", r"\1", text)

    # Table pipes
    text = re.sub(r"\|", " ", text)

    # Gabungkan baris -> prose
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = ". ".join(lines)

    # Rapikan duplikasi titik & spasi
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+\.", ".", text)

    return text.strip()


def clean_passage_and_samples(main_answer: str, samples: list[str]) -> tuple[str, list[str]]:
    cleaned_main = strip_markdown_for_nlp(main_answer)
    cleaned_samples = [strip_markdown_for_nlp(s) for s in samples]
    return cleaned_main, cleaned_samples