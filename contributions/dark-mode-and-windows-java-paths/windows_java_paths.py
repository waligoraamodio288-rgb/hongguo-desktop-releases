"""Keep the bundled Windows JVM's native-library paths ANSI-compatible."""
import os
from pathlib import Path
import subprocess


def java_runtime(root, data):
    """Return the same JRE through a validated persistent directory junction.

    Windows Java expands 8.3 paths before loading native DLLs. A directory
    junction retains its ASCII spelling, without moving or copying the JRE.
    Existing unrelated paths are rejected and never removed or replaced.
    """
    source = (Path(root) / "jre").resolve(strict=True)
    if os.name != "nt":
        return source
    try:
        str(source).encode("mbcs", errors="strict")
        return source
    except UnicodeEncodeError:
        pass

    data = Path(data)
    if not data.is_absolute():
        raise ValueError("An absolute runtime data directory is required")
    alias = data.resolve() / "runtime-links" / "jre"
    try:
        str(alias).encode("mbcs", errors="strict")
    except UnicodeEncodeError:
        raise RuntimeError("The runtime alias directory needs an ANSI-compatible path") from None

    if not os.path.lexists(alias):
        alias.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["HONGGUO_JRE_SOURCE"] = str(source)
        environment["HONGGUO_JRE_LINK"] = str(alias)
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run(
            [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
             "New-Item -ItemType Junction -Path $env:HONGGUO_JRE_LINK "
             "-Target $env:HONGGUO_JRE_SOURCE -ErrorAction Stop | Out-Null"],
            env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError("Could not create the bundled JVM runtime alias")

    try:
        correct = alias.is_dir() and os.path.samefile(alias, source)
    except OSError:
        correct = False
    if not correct:
        raise RuntimeError("The existing JVM runtime alias has a different target")
    return alias
