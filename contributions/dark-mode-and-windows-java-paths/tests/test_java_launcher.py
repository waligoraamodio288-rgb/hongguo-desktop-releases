"""Local regression tests: no user DB/config edits or HTTP/content requests.

Set HONGGUO_TEST_BACKEND to the installed backend directory. The owned local
signer test binds port 0, makes no requests, and terminates only its own child.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest


BACKEND = Path(os.environ["HONGGUO_TEST_BACKEND"]) if os.environ.get("HONGGUO_TEST_BACKEND") else None
PACKAGE = Path(__file__).resolve().parents[1]
bootstrap = None
if BACKEND is not None:
    spec = importlib.util.spec_from_file_location(
        "desktop_bootstrap_under_test", BACKEND / "desktop_bootstrap.py"
    )
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)


def runtime_helper():
    path = PACKAGE / "windows_java_paths.py"
    spec = importlib.util.spec_from_file_location("java_runtime_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(os.name == "nt" and BACKEND is not None, "Set HONGGUO_TEST_BACKEND on Windows")
class JavaLauncherRegressionTests(unittest.TestCase):
    def test_persistent_jre_alias_can_start_owned_signer(self):
        module_path = PACKAGE / "windows_java_paths.py"
        self.assertTrue(module_path.is_file(), "Missing persistent JVM runtime path adapter")
        runtime_module = runtime_helper()
        runtime = runtime_module.java_runtime(BACKEND, PACKAGE / "test-app-data")
        self.assertTrue(os.path.samefile(runtime, BACKEND / "jre"))
        process = subprocess.Popen(
            [str(runtime / "bin/java.exe"), "-Djava.net.preferIPv4Stack=true",
             "--add-opens", "java.base/java.lang=ALL-UNNAMED", "-Xmx512m",
             "-XX:+ExitOnOutOfMemoryError", "-cp", "unidbg-sign.jar",
             "com.hongguo.sign.FqTrace", "serve", "0"],
            cwd=BACKEND / "sign", stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            try:
                port = bootstrap.wait_signer(process, timeout=35)
            except RuntimeError as error:
                self.fail(f"Owned signer did not start: exit={process.poll()}, {error}")
            self.assertGreater(port, 0)
            self.assertIsNone(process.poll())
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)

    def test_unicode_install_can_load_its_bundled_jvm(self):
        # Returning the original Unicode runtime reproduces java.dll failure.
        runtime = runtime_helper().java_runtime(BACKEND, PACKAGE / "test-app-data")
        self.assertTrue(os.path.samefile(runtime, BACKEND / "jre"))
        result = subprocess.run(
            [str(runtime / "bin" / "java.exe"), "-version"],
            cwd=BACKEND / "sign",
            capture_output=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        detail = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, detail)
        self.assertIn("OpenJDK", detail)

    def test_existing_unrelated_alias_is_preserved(self):
        try:
            str((BACKEND / "jre").resolve()).encode("mbcs", errors="strict")
        except UnicodeEncodeError:
            pass
        else:
            self.skipTest("The runtime path is already ANSI-compatible; no alias is needed")
        data = PACKAGE / "test-unrelated-app-data"
        alias = data / "runtime-links" / "jre"
        alias.mkdir(parents=True, exist_ok=True)
        marker = alias / "preserve.txt"
        marker.write_text("existing unrelated directory", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "different target"):
            runtime_helper().java_runtime(BACKEND, data)
        self.assertEqual(marker.read_text(encoding="utf-8"), "existing unrelated directory")

    def test_verbatim_drive_path_is_normalized(self):
        self.assertEqual(
            bootstrap.launcher_path(r"\\?\C:\Program Files\Java\bin\java.exe"),
            r"C:\Program Files\Java\bin\java.exe",
        )

    def test_verbatim_unc_path_is_normalized(self):
        self.assertEqual(
            bootstrap.launcher_path(r"\\?\UNC\server\share\java.exe"),
            r"\\server\share\java.exe",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
