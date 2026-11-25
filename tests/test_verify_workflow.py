"""离线校验 scripts/verify_workflow.py 的 --static 逻辑（不连 ComfyUI）。"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("verify_workflow", ROOT / "scripts" / "verify_workflow.py")
vw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vw)  # type: ignore[union-attr]


class StaticCheckTests(unittest.TestCase):
    def test_repo_workflows_pass(self):
        files = sorted((ROOT / "workflows").rglob("*.json"))
        self.assertTrue(files, "仓库里没有工作流文件")
        for path in files:
            problems = vw.static_problems(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(problems, [], f"{path.relative_to(ROOT)}: {problems}")

    def test_dangling_api_reference_is_reported(self):
        wf = {"1": {"class_type": "X", "inputs": {"model": ["99", 0]}}}
        problems = vw.static_problems(wf)
        self.assertTrue(any("99" in p for p in problems), problems)

    def test_gui_link_to_missing_node_is_reported(self):
        wf = {"nodes": [{"id": 1, "type": "A"}], "links": [[1, 1, 0, 2, 0, "*"]]}
        problems = vw.static_problems(wf)
        self.assertTrue(any("2" in p for p in problems), problems)

    def test_gui_duplicate_node_ids_are_reported(self):
        wf = {"nodes": [{"id": 1, "type": "A"}, {"id": 1, "type": "B"}], "links": []}
        self.assertTrue(any("重复" in p for p in vw.static_problems(wf)))

    def test_unknown_format_is_reported(self):
        self.assertTrue(vw.static_problems({"hello": "world"}))


if __name__ == "__main__":
    unittest.main()
