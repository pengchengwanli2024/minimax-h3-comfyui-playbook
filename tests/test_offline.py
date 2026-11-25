"""离线自检：不连 ComfyUI，验证工作流结构、预设参数、帧网格与模型清单。

运行:
  python -m unittest discover -s tests -v
"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 从 scripts/ 目录按文件路径导入 run_batch（scripts 不是 package）
_spec = importlib.util.spec_from_file_location("run_batch", ROOT / "scripts" / "run_batch.py")
run_batch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_batch)  # type: ignore[union-attr]

FRAMES_GRID = [5, 22, 39, 56, 73, 90, 107, 124, 141, 158, 175, 192, 209, 226, 243,
               260, 277, 294, 311, 328, 345, 362]


def loop_targets(wf: dict):
    """遍历所有形如 ["node_id", slot] 的输入引用。"""
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            if len(o) == 2 and isinstance(o[0], str) and isinstance(o[1], int):
                yield o[0], o[1]
            for v in o:
                yield from walk(v)
    for node in wf.values():
        yield from walk(node.get("inputs", {}))


class WorkflowBuildTests(unittest.TestCase):
    def jobs(self):
        return json.loads((ROOT / "prompts" / "examples.json").read_text(encoding="utf-8"))

    def test_all_presets_build(self):
        for preset_name, preset in run_batch.PRESETS.items():
            for job in self.jobs()[:2]:
                job = dict(job)
                if preset["i2v"]:
                    job["image"] = "first_frame.png"
                wf = run_batch.build_prompt(preset, job)
                self.assertIn("8", wf, f"{preset_name}: 缺条件节点")
                self.assertIn("4", wf, f"{preset_name}: 缺 SigmaShift")

    def test_every_link_points_to_existing_node(self):
        for preset_name, preset in run_batch.PRESETS.items():
            job = dict(self.jobs()[0])
            if preset["i2v"]:
                job["image"] = "first_frame.png"
            wf = run_batch.build_prompt(preset, job)
            for node_id, slot in loop_targets(wf):
                self.assertIn(node_id, wf, f"{preset_name}: 引用了不存在的节点 {node_id}")
                self.assertIsInstance(slot, int)

    def test_required_nodes_present(self):
        required = {"UNETLoader", "CLIPLoader", "MiniMaxH3ImageToVideo", "MiniMaxH3SigmaShift",
                    "BasicScheduler", "KSamplerSelect", "BasicGuider", "SamplerCustomAdvanced",
                    "VAEDecode", "VAEDecodeAudio", "CreateVideo", "SaveVideo"}
        for preset_name, preset in run_batch.PRESETS.items():
            job = dict(self.jobs()[0])
            if preset["i2v"]:
                job["image"] = "first_frame.png"
            types = {n["class_type"] for n in run_batch.build_prompt(preset, job).values()}
            missing = required - types
            self.assertFalse(missing, f"{preset_name} 缺节点: {missing}")

    def test_attention_matches_preset(self):
        job = dict(self.jobs()[0])
        wf = run_batch.build_prompt(run_batch.PRESETS["turbo8_sla"], job)
        self.assertEqual(wf["3"]["inputs"]["selection"], "sla")
        wf = run_batch.build_prompt(run_batch.PRESETS["fasth3_vsa"], job)
        self.assertEqual(wf["3"]["inputs"]["selection"], "vsa")
        wf = run_batch.build_prompt(run_batch.PRESETS["i2v_turbo8"], job | {"image": "x.png"})
        self.assertNotIn("3", wf, "i2v 预设不应带稀疏注意力")

    def test_i2v_requires_image(self):
        with self.assertRaises(SystemExit):
            run_batch.build_prompt(run_batch.PRESETS["i2v_turbo8"], dict(self.jobs()[0]))


class ExampleJobTests(unittest.TestCase):
    def test_frame_length_on_grid(self):
        jobs = json.loads((ROOT / "prompts" / "examples.json").read_text(encoding="utf-8"))
        for j in jobs:
            self.assertIn(j["length"], FRAMES_GRID, f"{j['name']} 帧数 {j['length']} 不在 17k+5 网格")

    def test_dimensions_multiple_of_32(self):
        jobs = json.loads((ROOT / "prompts" / "examples.json").read_text(encoding="utf-8"))
        for j in jobs:
            for key in ("width", "height"):
                self.assertEqual(j[key] % 32, 0, f"{j['name']}: {key}={j[key]} 不是 32 的倍数")
            self.assertLessEqual(min(j["width"], j["height"]), 768, f"{j['name']}: 短边超过 768")

    def test_prompts_have_shot_structure(self):
        jobs = json.loads((ROOT / "prompts" / "examples.json").read_text(encoding="utf-8"))
        for j in jobs:
            self.assertIn("integrated_multimodal_description", j["prompt"])


class AssetTests(unittest.TestCase):
    def test_models_manifest(self):
        data = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        self.assertTrue(data["sets"])
        for name, spec in data["sets"].items():
            self.assertIn("files", spec, name)
            for f in spec["files"]:
                for key in ("repo", "path", "dest", "size_gb"):
                    self.assertIn(key, f, f"{name} 缺字段 {key}")
                self.assertTrue(f["dest"].endswith((".safetensors", ".gguf")), f["dest"])
                self.assertGreater(f["size_gb"], 0)

    def test_api_workflows_parse(self):
        for path in sorted((ROOT / "workflows" / "api").glob("*.json")):
            wf = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(all(isinstance(v, dict) and "class_type" in v for v in wf.values()),
                            f"{path.name} 不是 API 格式")
            for node_id, slot in loop_targets(wf):
                self.assertIn(node_id, wf, f"{path.name}: 引用不存在的节点 {node_id}")

    def test_gui_workflow_has_nodes(self):
        path = ROOT / "workflows" / "gui" / "H3_4step_VSA_T2V_1152x640_10s.json"
        wf = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("nodes", wf)
        self.assertIn("links", wf)
        self.assertTrue(wf.get("definitions", {}).get("subgraphs"), "GUI 工作流应为子图模板")

    def test_docs_exist(self):
        for rel in ("README.md", "LICENSE", "NOTICE.md", "docs/parameters.md",
                    "docs/troubleshooting.md", "docs/benchmarks.md"):
            self.assertTrue((ROOT / rel).exists(), f"缺文件 {rel}")


if __name__ == "__main__":
    unittest.main()
