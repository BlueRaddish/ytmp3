"""Run the production Java report store against real temporary files; requires JDK17+."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
for tool in ["javac", "java"]:
    if not shutil.which(tool):
        raise RuntimeError(f"{tool} is required for playback report store verification")
with tempfile.TemporaryDirectory(prefix="ytmp3-report-check-") as temp:
    subprocess.run(["javac", "-d", temp,
        str(ROOT / "android/app/src/main/java/io/github/blueraddish/ytmp3/PlaybackReportStore.java"),
        str(ROOT / "tests/java/PlaybackReportStoreCheck.java")], check=True, timeout=30, creationflags=flags)
    result = subprocess.run(["java", "-ea", "-Xmx96m", "-cp", temp,
        "io.github.blueraddish.ytmp3.PlaybackReportStoreCheck", str(Path(temp) / "data")],
        check=True, timeout=30, creationflags=flags, capture_output=True, text=True)
    if "PASS:" not in result.stdout:
        raise RuntimeError(f"Java report checks returned no completion receipt: {result.stdout!r} {result.stderr!r}")
    print(result.stdout.strip())
