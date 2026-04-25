"""Load the narrative prompt once at module import.

D-10: externalised prompt.txt — avoids Python-string-escaping pain for exemplars,
makes copy review cleaner in PR diff, and the prompt freezes as an independent
artefact at DEMO-04.
"""
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_prompt() -> str:
    """Return the contents of agent/narrative/prompt.txt.

    Uses a path anchored to this module so imports succeed whether cwd is
    /app (AgentCore runtime), the repo root (tests), or elsewhere.
    """
    with open(os.path.join(_THIS_DIR, "prompt.txt"), encoding="utf-8") as f:
        return f.read()


# Module-level cache — load once at import, reused across invocations.
NARRATIVE_PROMPT: str = load_prompt()
