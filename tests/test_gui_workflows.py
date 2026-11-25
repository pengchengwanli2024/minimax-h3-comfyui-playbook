"""GUI 工作流自检：结构、子图引用、模型文件名与仓库清单一致。"""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_workflow", ROOT / "scripts" / "verify_workflow.py")
vw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vw)  # type: ignore[union-attr]

GUI = ROOT / "workflows" / "gui"
MANIFEST = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
MODEL_FIELDS = {
    "UNETLoader": "unet_name",
    "CLIPLoader": "clip_name",
    "VAELoader": "vae_name",
    "LoraLoaderModelOnly": "lora_name",
    "LoraLoader": "lora_name",
}


def manifest_models():
    names = set()
    for model_set in MANIFEST["sets"].values():
        for item in model_set["files"]:
            names.add(item["path"].split("/")[-1])
            names.add(item["dest"].split("/")[-1])
    return names


class GuiWorkflowTests(unittest.TestCase):
    def gui_files(self):
        return sorted(GUI.glob("*.json"))

    def test_gui_workflows_exist(self):
        self.assertGreaterEqual(len(self.gui_files()), 3, "GUI 工作流不足 3 个")

    def test_structures_pass_static_check(self):
        for path in self.gui_files():
            wf = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(vw.static_problems(wf), [], path.name)

    def test_model_filenames_exist_in_manifest(self):
        known = manifest_models()
        for path in sorted((ROOT / "workflows").rglob("*.json")):
            text = path.read_text(encoding="utf-8")
            for name in set(re.findall(r"[A-Za-z0-9_.\-]+\.(?:safetensors|gguf)", text)):
                self.assertIn(name, known, f"{path.relative_to(ROOT)} 引用了 models.json 里没有的模型: {name}")

    def test_property_models_match_widgets(self):
        for path in self.gui_files():
            wf = json.loads(path.read_text(encoding="utf-8"))
            nodes = list(wf["nodes"])
            for sg in (wf.get("definitions") or {}).get("subgraphs") or []:
                nodes += sg["nodes"]
            for node in nodes:
                if node.get("type") not in MODEL_FIELDS:
                    continue
                models = (node.get("properties") or {}).get("models") or []
                if not models:
                    continue
                widget = (node.get("widgets_values") or [None])[0]
                self.assertEqual(models[0].get("name"), widget,
                                 f"{path.name}: 节点 {node['id']} 的 properties.models 与下拉值不一致")

    def test_image_to_video_workflow_is_wired(self):
        candidates = [p for p in self.gui_files() if "i2v" in p.name]
        self.assertTrue(candidates, "缺少图生视频 GUI 工作流")
        for path in candidates:
            wf = json.loads(path.read_text(encoding="utf-8"))
            nodes = {n["id"]: n for n in wf["nodes"]}
            links = {link[0]: link for link in wf["links"]}
            loaders = [n for n in wf["nodes"] if n.get("type") == "LoadImage"]
            self.assertEqual(len(loaders), 1, f"{path.name}: 应有一个 LoadImage")
            loader = loaders[0]
            self.assertTrue((loader.get("widgets_values") or [""])[0].strip(), "LoadImage 没设置默认图片名")
            wired = False
            for link_id in (loader.get("outputs") or [{}])[0].get("links") or []:
                link = links.get(link_id)
                target = nodes.get(link[3]) if link else None
                if target and link[4] == 0 and (target.get("inputs") or [{}])[0].get("name") == "first_frame":
                    wired = True
            self.assertTrue(wired, f"{path.name}: LoadImage 没有接到子图的 first_frame")
            saves = [n for n in wf["nodes"] if n.get("type") == "SaveVideo"]
            self.assertTrue(saves and "i2v" in (saves[0].get("widgets_values") or [""])[0],
                            f"{path.name}: SaveVideo 的输出前缀里应带 i2v")

    def test_each_gui_has_notes_and_prompt(self):
        for path in self.gui_files():
            wf = json.loads(path.read_text(encoding="utf-8"))
            notes = [n for n in wf["nodes"] if n.get("type") == "MarkdownNote"]
            self.assertGreaterEqual(len(notes), 2, f"{path.name}: 至少应有两个说明节点")
            for note in notes:
                self.assertTrue((note.get("widgets_values") or [""])[0].strip(), f"{path.name}: 说明节点内容为空")


if __name__ == "__main__":
    unittest.main()
