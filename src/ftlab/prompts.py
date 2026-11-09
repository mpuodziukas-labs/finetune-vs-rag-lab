"""Prompt builders. Fine-tuned model gets the short prompt (that is its advantage);
zero-shot and retrieval need the label list in the prompt."""


def _header(words: list[str]) -> str:
    return "Classify the banking message into one intent: " + ", ".join(words) + ".\n\n"


def tuned(text: str) -> str:
    return f"Message: {text}\nIntent:"


def zero_shot(text: str, words: list[str]) -> str:
    return _header(words) + tuned(text)


def few_shot(text: str, demos: list[tuple[str, str]], words: list[str]) -> str:
    """demos: (message, label word), best match last (closest to the query)."""
    body = "".join(f"Message: {t}\nIntent: {w}\n\n" for t, w in demos)
    return _header(words) + body + tuned(text)
