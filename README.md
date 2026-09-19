# dotlinks

A small library for answering one question: are the symlinks in your home
directory actually pointing at the files in your dotfiles repo, or have they
drifted?

I keep dotfiles in a plain directory (`~/dotfiles/zshrc`, `~/dotfiles/gitconfig`,
and so on) and symlink each one into `$HOME` as `.zshrc`, `.gitconfig`, etc.
That works fine until something reinstalls a package that overwrites
`~/.gitconfig` with a real file, or a symlink ends up pointing at the wrong
repo after a move. `dotlinks` scans the repo, figures out what each symlink
*should* be, and reports what it actually is.

This is a library, not a command-line tool. Wire it into your own script.

## Install

No PyPI package yet. Drop `src/dotlinks` on your `PYTHONPATH`, or install
from a local checkout:

```
pip install -e .
```

Zero third-party dependencies; standard library only.

## Usage

```python
from pathlib import Path
import dotlinks

specs = dotlinks.discover(Path("~/dotfiles"))
results = dotlinks.check_all(specs)

print(dotlinks.format(results))
```

Output:

```
gitconfig  ok
tmux.conf  missing
vimrc      wrong  (points at /Users/me/old-dotfiles/vimrc)
zshrc      occupied  (/Users/me/.zshrc is a real file, not a symlink)
```

## The --json mode

`dotlinks` itself has no CLI, but every result is built to be forwarded
straight into a `--json` flag on whatever tool you put on top of it:

```python
import argparse
import dotlinks
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

results = dotlinks.check_all(dotlinks.discover(Path("~/dotfiles")))
print(dotlinks.format(results, as_json=args.json))
```

With `--json`, each entry looks like:

```json
{
  "name": "vimrc",
  "source": "/Users/me/dotfiles/vimrc",
  "target": "/Users/me/.vimrc",
  "state": "wrong_target",
  "detail": "points at /Users/me/old-dotfiles/vimrc"
}
```

`state` is always one of `ok`, `missing`, `wrong_target`, `occupied`, `broken`,
so downstream tooling can match on it without parsing the detail string.

## Fixing links

`apply()` takes a single `LinkResult` and makes the filesystem match it:
`missing` links get created, `wrong_target` and `broken` links get replaced.
`ok` results are a no-op. `occupied` results are left alone and raise
`FileExistsError` unless you pass `force=True`, since something not managed
by dotlinks is sitting on the target.

```python
results = dotlinks.check_all(dotlinks.discover(Path("~/dotfiles")))
fixed = dotlinks.apply_all(results)
print(dotlinks.format(fixed))
```

`apply_all` applies `apply` to every result and returns the resulting list,
so you can check() before and after and diff the two reports.

## Status

Early skeleton. `discover` only handles a flat directory of files today;
nested dotfiles repos come next.
