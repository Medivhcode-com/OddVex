"""Rule-based assistant. No language model is connected.

Pipeline: deterministic intent router -> internal data tools (which call the
same read models and quant functions as the rest of the API) -> a templated
explanation. An LLM could later replace the :class:`Explainer` to phrase the
tool output, but it would never be the source of a number.
"""

from .engine import Assistant, ToolResult
from .explainer import Explainer, TemplateExplainer

__all__ = ["Assistant", "Explainer", "TemplateExplainer", "ToolResult"]
