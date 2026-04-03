"""
AST-safe arithmetic expression evaluator.
Never calls eval() — walks only numeric/operator AST nodes.
"""
from __future__ import annotations
import ast
from crewai.tools import tool

_ALLOWED_OPS = (
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow, ast.UAdd, ast.USub,
)


def _eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("disallowed")
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_OPS):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op = node.op
        if isinstance(op, ast.Add):      return left + right
        if isinstance(op, ast.Sub):      return left - right
        if isinstance(op, ast.Mult):     return left * right
        if isinstance(op, ast.Div):      return left / right
        if isinstance(op, ast.FloorDiv): return left // right
        if isinstance(op, ast.Mod):      return left % right
        if isinstance(op, ast.Pow):      return left ** right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        val = _eval_node(node.operand)
        return val if isinstance(node.op, ast.UAdd) else -val
    raise ValueError("disallowed")


@tool("calculator")
def calculator_tool(expression: str) -> str:
    """Evaluate a math expression safely using AST (no eval). Args: expression."""
    if not expression or not expression.strip():
        return "Error: expression must be a non-empty string"
    if "\x00" in expression:
        return "Error: expression contains invalid characters"
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        return "Error: invalid expression"
    try:
        result = _eval_node(tree)
        return str(result)
    except ZeroDivisionError:
        return "Error: division by zero"
    except ValueError:
        return "Error: expression contains disallowed operations"
    except Exception:
        return "Error: invalid expression"
