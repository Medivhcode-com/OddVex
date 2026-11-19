"""Rule-based assistant. No language model is connected.

Pipeline: responsible-gambling checks -> deterministic intent router -> internal
data tools (which call the same read models and quant functions as the rest of
the API) -> a templated explanation. An LLM could later replace the
:class:`Explainer` to phrase the tool output, but it would never be the source
of a number.

The checks (``safeguards.py``) run first on every message. Crisis or self-harm
language, distress about gambling and a user who says they are under 21 each get
a fixed support reply with no betting data; a request for a certain winner gets
a fixed refusal. Those replies do not go through the :class:`Explainer`.
"""

from .engine import Assistant, ToolResult
from .explainer import Explainer, TemplateExplainer

__all__ = ["Assistant", "Explainer", "TemplateExplainer", "ToolResult"]
