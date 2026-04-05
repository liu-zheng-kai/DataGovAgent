import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
MYSQL = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")


def run(cmd, cwd=None):
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def main():
    print("python_exe", sys.executable)
    code, out, err = run([sys.executable, "--version"])
    print("python_version", out or err)

    code, out, err = run([str(VENV_PYTHON), "--version"])
    print("venv_python", out or err)

    code, out, err = run([str(VENV_PYTHON), "-m", "pip", "--version"])
    print("venv_pip", out or err)

    code, out, err = run(
        [
            str(MYSQL),
            "-h",
            "127.0.0.1",
            "-P",
            "3306",
            "-u",
            "root",
            "-proot",
            "-e",
            "SHOW DATABASES LIKE 'metadata_governance';",
        ]
    )
    print("mysql_db_check", "ok" if code == 0 and "metadata_governance" in out else "failed")
    if out:
        print(out)
    if err:
        print(err)

    code, out, err = run(
        [
            str(VENV_PYTHON),
            "-c",
            "import fastapi,sqlalchemy,openai,pymysql; print('imports_ok')",
        ],
        cwd=PROJECT_ROOT,
    )
    print("python_imports", out or err)


if __name__ == "__main__":
    main()
