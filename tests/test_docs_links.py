"""检查 Markdown 里的相对链接是否指向真实存在的文件（防止文档腐化）。"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIX = ("http://", "https://", "mailto:", "#")


def md_files():
    return [p for p in ROOT.rglob("*.md") if ".git" not in p.parts]


class DocsLinkTests(unittest.TestCase):
    def test_relative_links_exist(self):
        broken = []
        for md in md_files():
            base = md.parent
            for raw in LINK_RE.findall(md.read_text(encoding="utf-8")):
                target = raw.split("#", 1)[0].strip()
                if not target or target.startswith(SKIP_PREFIX) or "://" in target:
                    continue
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1]
                path = (base / target).resolve()
                if not path.exists():
                    broken.append(f"{md.relative_to(ROOT)} -> {raw}")
        self.assertFalse(broken, "存在失效的文档链接:\n" + "\n".join(broken))

    def test_readme_language_switch(self):
        zh = (ROOT / "README.md").read_text(encoding="utf-8")
        en = (ROOT / "README.en.md").read_text(encoding="utf-8")
        self.assertIn("[English](README.en.md)", zh)
        self.assertIn("[中文](README.md)", en)

    def test_docs_indexed(self):
        zh = (ROOT / "README.md").read_text(encoding="utf-8")
        for rel in ("docs/parameters.md", "docs/troubleshooting.md", "docs/benchmarks.md",
                    "docs/article-notes.md", "docs/version-compat.md", "docs/faq.md",
                    "CONTRIBUTING.md"):
            self.assertIn(rel, zh, f"README 没有链接 {rel}")


if __name__ == "__main__":
    unittest.main()
