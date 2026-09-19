"""Discover dotfile mappings and check their symlink state against the filesystem."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


class LinkState(Enum):
    OK = "ok"                       # symlink exists and points at the expected source
    MISSING = "missing"             # nothing at all sits at the target path
    WRONG_TARGET = "wrong_target"   # a symlink exists but points somewhere else
    OCCUPIED = "occupied"           # target exists and is a real file/dir, not a symlink
    BROKEN = "broken"               # a symlink exists but what it points at is gone


@dataclass(frozen=True)
class LinkSpec:
    """One dotfile mapping: a file that lives in the dotfiles repo and where it should be linked."""

    name: str    # relative name inside the source dir, e.g. "zshrc"
    source: Path  # absolute path to the real file
    target: Path  # absolute path where the symlink is expected, e.g. ~/.zshrc


@dataclass(frozen=True)
class LinkResult:
    spec: LinkSpec
    state: LinkState
    detail: str = ""  # extra context, e.g. what a wrong symlink actually points at


def discover(source_dir: Path, home: Path | None = None, skip: Iterable[str] = ()) -> list[LinkSpec]:
    """Build the dotfile -> home mapping from a flat dotfiles directory.

    Every regular file directly inside source_dir becomes a target named
    "." + filename under home. Subdirectories and names already starting
    with "." are skipped, since a dotfiles repo usually keeps its own
    tooling (.git, README, etc.) alongside the files it manages.
    """
    source_dir = source_dir.expanduser().resolve()
    home = (home or Path.home()).expanduser().resolve()
    skip_set = set(skip)

    specs = []
    for entry in sorted(source_dir.iterdir()):
        if entry.name in skip_set or entry.name.startswith("."):
            continue
        if not entry.is_file():
            continue
        specs.append(LinkSpec(name=entry.name, source=entry, target=home / f".{entry.name}"))
    return specs


def check(spec: LinkSpec) -> LinkResult:
    """Compare one spec against the filesystem and classify what is actually there."""
    if spec.target.is_symlink():
        raw = Path(os.readlink(spec.target))
        actual = raw if raw.is_absolute() else spec.target.parent / raw
        actual = actual.resolve()
        if not actual.exists():
            return LinkResult(spec, LinkState.BROKEN, detail=f"points at missing {actual}")
        if actual == spec.source.resolve():
            return LinkResult(spec, LinkState.OK)
        return LinkResult(spec, LinkState.WRONG_TARGET, detail=f"points at {actual}")

    if spec.target.exists():
        return LinkResult(spec, LinkState.OCCUPIED, detail=f"{spec.target} is a real file, not a symlink")

    return LinkResult(spec, LinkState.MISSING)


def check_all(specs: Iterable[LinkSpec]) -> list[LinkResult]:
    return [check(spec) for spec in specs]


def apply(result: LinkResult, *, force: bool = False) -> LinkResult:
    """Create or repair the symlink a check() result describes.

    OK results are returned unchanged. MISSING, WRONG_TARGET, and BROKEN are
    fixed by (re)creating the symlink at spec.target pointing at spec.source.
    OCCUPIED is left alone unless force is set, since something not managed
    by dotlinks is sitting on the target and silently deleting it would lose
    whatever that was.
    """
    spec = result.spec

    if result.state == LinkState.OK:
        return result

    if result.state == LinkState.OCCUPIED and not force:
        raise FileExistsError(
            f"{spec.target} is a real file or directory, not a symlink; "
            "pass force=True to replace it"
        )

    if result.state in (LinkState.WRONG_TARGET, LinkState.BROKEN, LinkState.OCCUPIED):
        if spec.target.is_symlink() or not spec.target.is_dir():
            spec.target.unlink()
        else:
            shutil.rmtree(spec.target)

    spec.target.parent.mkdir(parents=True, exist_ok=True)
    spec.target.symlink_to(spec.source)
    return check(spec)


def apply_all(results: Iterable[LinkResult], *, force: bool = False) -> list[LinkResult]:
    return [apply(result, force=force) for result in results]
