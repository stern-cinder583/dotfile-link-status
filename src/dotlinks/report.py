"""Turn LinkResults into either a human-readable table or JSON.

This is the piece any caller-facing tool built on top of dotlinks will
want to expose as a --json flag: call format() with as_json set from
the flag and print the result, nothing else needed.
"""

from __future__ import annotations

import json

from .core import LinkResult, LinkState

_LABELS = {
    LinkState.OK: "ok",
    LinkState.MISSING: "missing",
    LinkState.WRONG_TARGET: "wrong",
    LinkState.OCCUPIED: "occupied",
    LinkState.BROKEN: "broken",
}


def to_dict(result: LinkResult) -> dict:
    return {
        "name": result.spec.name,
        "source": str(result.spec.source),
        "target": str(result.spec.target),
        "state": result.state.value,
        "detail": result.detail,
    }


def format_text(results: list[LinkResult]) -> str:
    if not results:
        return "no dotfiles found"

    width = max(len(r.spec.name) for r in results)
    lines = []
    for r in results:
        line = f"{r.spec.name.ljust(width)}  {_LABELS[r.state]}"
        if r.detail:
            line += f"  ({r.detail})"
        lines.append(line)
    return "\n".join(lines)


def format_json(results: list[LinkResult]) -> str:
    return json.dumps([to_dict(r) for r in results], indent=2)


def format(results: list[LinkResult], as_json: bool = False) -> str:
    return format_json(results) if as_json else format_text(results)
