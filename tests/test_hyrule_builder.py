import tempfile
import unittest
from pathlib import Path
from hyrule_builder.runtime import HOOKSHOT_TAG, SUPPORTED_LANGUAGES, app_data_root, build_environment, check_arguments, cpu_target_from_name, source_arguments, tools_root

class RuntimeTests(unittest.TestCase):
    def test_supported_upstream_pin(self):
        self.assertEqual(HOOKSHOT_TAG,"v2.1.0")
    def test_cpu_target_is_only_set_for_known_zen3_models(self):
        self.assertEqual(cpu_target_from_name("AMD Ryzen 7 6800H with Radeon Graphics"),"znver3")
        self.assertIsNone(cpu_target_from_name("AMD Ryzen 7 7840HS"))
        self.assertIsNone(cpu_target_from_name("Intel Core i7-12700H"))
    def test_paths_are_isolated(self):
        base=app_data_root({"LOCALAPPDATA":r"C:\Users\Tester\AppData\Local"})
        self.assertEqual(base.name,"HyruleBuilder")
        self.assertEqual(tools_root(base).name,"tools")
    def test_nup_args(self):
        args=source_arguments(nup="C:/Dumps/user.nup",output="C:/Games/Hyrule",prepare_shaders=False)
        self.assertIn("--nup",args); self.assertIn("--no-prepare-shaders",args)
        self.assertEqual(check_arguments(nup="C:/Dumps/user.nup")[:2],["--check","--nup"])
    def test_extracted_folder_args(self):
        args=source_arguments(romfs="C:/Dump/romfs",exefs="C:/Dump/exefs",output="C:/Games/Hyrule")
        self.assertIn("--romfs",args); self.assertIn("--exefs",args)
    def test_requires_both_extracted_folders(self):
        with self.assertRaises(ValueError):source_arguments(romfs="C:/Dump/romfs",output="out")
    def test_language_is_validated(self):
        self.assertIn("en-US",SUPPORTED_LANGUAGES)
        with self.assertRaises(ValueError):source_arguments(nup="a.nup",output="out",language="not-a-language")
    def test_build_environment_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            tool=Path(td)
            for n in ("emsdk","cpm","wgpu-native"):(tool/n).mkdir()
            env=build_environment(tool,launcher_exe="HyruleBuilder.exe",environ={"LOCALAPPDATA":td,"RX_MARCH":"unsafe"},cpu_target="znver3")
            self.assertEqual(env["A64_POLL_INTERVAL"],"1"); self.assertEqual(env["A64_POLL_HOT_ONLY"],"1")
            self.assertEqual(env["RX_HOT_OPT"],"O2"); self.assertEqual(env["RX_MARCH"],"znver3")
            self.assertIn("HOOKSHOT_BUILDER_EXE",env); self.assertTrue(env["EMSDK"].endswith("emsdk"))

if __name__=="__main__":unittest.main()
