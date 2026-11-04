import unittest

from utils.environment_lifecycle import managed_python_env


class ManagedEnvironmentIsolationTest(unittest.TestCase):
    def test_python_path_pollution_is_removed_without_losing_other_settings(self):
        source = {
            "PATH": "managed-bin;system-bin",
            "PYTHONPATH": r"C:\python3.11.4\Lib\site-packages",
            "PYTHONHOME": r"C:\python3.11.4",
            "PythonPath": r"C:\another-global-site-packages",
            "HTTPS_PROXY": "http://127.0.0.1:7890",
            "CUDA_VISIBLE_DEVICES": "0",
        }

        isolated = managed_python_env(source)

        self.assertNotIn("PYTHONPATH", isolated)
        self.assertNotIn("PYTHONHOME", isolated)
        self.assertNotIn("PythonPath", isolated)
        self.assertEqual(isolated["PYTHONNOUSERSITE"], "1")
        self.assertEqual(isolated["PATH"], source["PATH"])
        self.assertEqual(isolated["HTTPS_PROXY"], source["HTTPS_PROXY"])
        self.assertEqual(isolated["CUDA_VISIBLE_DEVICES"], "0")
        self.assertIn("PYTHONPATH", source, "the caller's mapping must not be mutated")


if __name__ == "__main__":
    unittest.main()
