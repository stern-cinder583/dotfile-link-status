import tempfile
import unittest
from pathlib import Path

from dotlinks import LinkSpec, LinkState, apply, apply_all, check, check_all, discover


class TempDirCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve() because discover() does, and macOS temp dirs sit behind a symlink
        root = Path(tmp.name).resolve()
        self.source = root / "dotfiles"
        self.home = root / "home"
        self.source.mkdir()
        self.home.mkdir()

    def write(self, rel: str, text: str = "x") -> Path:
        path = self.source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def spec_for(self, rel: str) -> LinkSpec:
        specs = {s.name: s for s in discover(self.source, home=self.home)}
        return specs[rel]


class DiscoverTests(TempDirCase):
    def test_top_level_files_get_a_dot(self):
        src = self.write("zshrc")
        specs = discover(self.source, home=self.home)
        self.assertEqual(specs, [LinkSpec("zshrc", src, self.home / ".zshrc")])

    def test_only_top_component_is_dotted(self):
        src = self.write("vim/vimrc")
        specs = discover(self.source, home=self.home)
        self.assertEqual(specs, [LinkSpec("vim/vimrc", src, self.home / ".vim" / "vimrc")])

    def test_hidden_entries_are_pruned_at_any_depth(self):
        self.write(".git/config")
        self.write("vim/.netrwhist")
        self.write("vim/vimrc")
        names = [s.name for s in discover(self.source, home=self.home)]
        self.assertEqual(names, ["vim/vimrc"])

    def test_skip_applies_at_any_depth(self):
        self.write("README.md")
        self.write("config/README.md")
        self.write("config/app.toml")
        names = [s.name for s in discover(self.source, home=self.home, skip=["README.md"])]
        self.assertEqual(names, ["config/app.toml"])

    def test_results_are_sorted(self):
        for name in ("tmux.conf", "gitconfig", "zshrc"):
            self.write(name)
        names = [s.name for s in discover(self.source, home=self.home)]
        self.assertEqual(names, sorted(names))


class CheckTests(TempDirCase):
    def test_missing(self):
        self.write("zshrc")
        self.assertEqual(check(self.spec_for("zshrc")).state, LinkState.MISSING)

    def test_ok_with_absolute_link(self):
        src = self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(src)
        self.assertEqual(check(spec).state, LinkState.OK)

    def test_ok_with_relative_link(self):
        self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(Path("..") / "dotfiles" / "zshrc")
        self.assertEqual(check(spec).state, LinkState.OK)

    def test_wrong_target(self):
        self.write("zshrc")
        other = self.home / "other"
        other.write_text("y")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(other)
        result = check(spec)
        self.assertEqual(result.state, LinkState.WRONG_TARGET)
        self.assertIn(str(other), result.detail)

    def test_broken(self):
        self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(self.home / "gone")
        result = check(spec)
        self.assertEqual(result.state, LinkState.BROKEN)
        self.assertIn("gone", result.detail)

    def test_occupied(self):
        self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.write_text("local edits")
        self.assertEqual(check(spec).state, LinkState.OCCUPIED)

    def test_check_all_keeps_order(self):
        self.write("a")
        self.write("b")
        results = check_all(discover(self.source, home=self.home))
        self.assertEqual([r.spec.name for r in results], ["a", "b"])


class ApplyTests(TempDirCase):
    def test_creates_missing_link_and_parent_dirs(self):
        src = self.write("vim/vimrc")
        spec = self.spec_for("vim/vimrc")
        result = apply(check(spec))
        self.assertEqual(result.state, LinkState.OK)
        self.assertTrue(spec.target.is_symlink())
        self.assertEqual(spec.target.resolve(), src)

    def test_replaces_wrong_target(self):
        src = self.write("zshrc")
        other = self.home / "other"
        other.write_text("y")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(other)
        result = apply(check(spec))
        self.assertEqual(result.state, LinkState.OK)
        self.assertEqual(spec.target.resolve(), src)
        self.assertTrue(other.exists())

    def test_replaces_broken_link(self):
        self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(self.home / "gone")
        self.assertEqual(apply(check(spec)).state, LinkState.OK)

    def test_ok_is_untouched(self):
        src = self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.symlink_to(src)
        before = check(spec)
        self.assertIs(apply(before), before)

    def test_occupied_raises_and_keeps_file(self):
        self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.write_text("local edits")
        with self.assertRaises(FileExistsError):
            apply(check(spec))
        self.assertFalse(spec.target.is_symlink())
        self.assertEqual(spec.target.read_text(), "local edits")

    def test_force_replaces_occupied_file(self):
        src = self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.write_text("local edits")
        result = apply(check(spec), force=True)
        self.assertEqual(result.state, LinkState.OK)
        self.assertEqual(spec.target.resolve(), src)

    def test_force_replaces_occupied_directory(self):
        src = self.write("zshrc")
        spec = self.spec_for("zshrc")
        spec.target.mkdir()
        (spec.target / "inner").write_text("z")
        result = apply(check(spec), force=True)
        self.assertEqual(result.state, LinkState.OK)
        self.assertEqual(spec.target.resolve(), src)

    def test_apply_all(self):
        self.write("a")
        self.write("b")
        results = apply_all(check_all(discover(self.source, home=self.home)))
        self.assertTrue(all(r.state == LinkState.OK for r in results))


if __name__ == "__main__":
    unittest.main()
