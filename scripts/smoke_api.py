import subprocess
import time
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def main():
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--port", "8010"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8010/health", timeout=2) as r:
                    print(r.read().decode("utf-8"))
                    return
            except Exception:
                time.sleep(1)
        raise RuntimeError("health check timeout")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
