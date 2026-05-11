"""Reusable tools for harness-based quest agents."""

import ast
import re

MAX_SCRATCHPAD_CHARS = 1200


def calculator(expression: str) -> str:
    """Evaluate a restricted arithmetic/comparison expression."""
    expr = (expression or "").strip()
    if not expr:
        return "error: empty expression"
    if len(expr) > 240:
        return "error: expression too long"
    if not re.fullmatch(r"[0-9a-zA-Z\s+\-*/().,<>=!%]+", expr):
        return "error: unsupported characters"

    allowed_nodes = (
        ast.Expression,
        ast.Constant,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.BoolOp,
        ast.And,
        ast.Or,
    )
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                return f"error: unsupported expression element {node.__class__.__name__}"
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
                return "error: constants must be numeric or boolean"
        result = _eval_calculator_node(tree.body)
    except Exception as exc:
        return f"error: {exc}"
    return f"{expr} = {result}"


def _eval_calculator_node(node: ast.AST) -> int | float | bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
        return node.value
    if isinstance(node, ast.UnaryOp):
        value = _eval_calculator_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.USub):
            return -value
    if isinstance(node, ast.BinOp):
        left = _eval_calculator_node(node.left)
        right = _eval_calculator_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 8:
                raise ValueError("exponent too large")
            return left**right
    if isinstance(node, ast.BoolOp):
        values = [bool(_eval_calculator_node(value)) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
    if isinstance(node, ast.Compare):
        left = _eval_calculator_node(node.left)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval_calculator_node(comparator)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            else:
                raise ValueError("unsupported comparison")
            if not ok:
                return False
            left = right
        return True
    raise ValueError("unsupported expression")


class Scratchpad:
    """Persistent free-form note blob with read and replace operations."""

    def __init__(self, max_chars: int = MAX_SCRATCHPAD_CHARS):
        self.max_chars = max_chars
        self._content = ""

    def read(self) -> str:
        return self._content or "(empty)"

    def write_replace(self, content: str = "") -> str:
        note = " ".join((content or "").strip().split())
        self._content = note[: self.max_chars]
        return f"updated: {self._content or '(empty)'}"

    def reset(self) -> None:
        self._content = ""


class QuestHistoryTool:
    """Keyword search over a run-local quest step log."""

    def __init__(self, step_log: list[dict] | None = None, history_window: int = 10):
        self.step_log = step_log if step_log is not None else []
        self.history_window = history_window

    def search(self, query: str) -> str:
        """Return relevant previous steps from this quest run via keyword match."""
        if not self.step_log:
            return "No prior quest steps recorded yet."

        tokens = set(re.findall(r"[a-zA-Z\u0400-\u04ff0-9_]{3,}", (query or "").lower()))
        scored = []
        for entry in self.step_log:
            haystack = " ".join(
                [
                    entry.get("observation", ""),
                    " ".join(entry.get("choices", [])),
                    entry.get("selected_choice", ""),
                ]
            ).lower()
            score = sum(1 for token in tokens if token in haystack)
            scored.append((score, entry))

        scored.sort(key=lambda item: (item[0], item[1].get("step", 0)), reverse=True)
        best = [entry for score, entry in scored if score > 0][: self.history_window]
        if not best:
            best = [entry for _, entry in scored[-self.history_window :]]

        lines = []
        for entry in best:
            lines.append(
                f"Step {entry['step']}: obs={entry['observation']} | "
                f"choices={'; '.join(entry['choices'])} | picked={entry.get('selected_choice', 'n/a')}"
            )
        return "\n".join(lines)
