import shutil
import subprocess
from pathlib import Path


MYSQL_BASE = Path(r"C:\Program Files\MySQL\MySQL Server 8.4")
MYSQLD = MYSQL_BASE / "bin" / "mysqld.exe"
MYSQL_HOME = Path(r"C:\ProgramData\MySQL\MySQL Server 8.4")
MY_INI = MYSQL_HOME / "my.ini"
DATA_DIR = MYSQL_HOME / "Data"


def run(cmd):
    print(">", " ".join(str(c) for c in cmd))
    p = subprocess.run(cmd, text=True, capture_output=True, encoding="utf-8", errors="ignore")
    if p.stdout.strip():
        print(p.stdout.strip())
    if p.stderr.strip():
        print(p.stderr.strip())
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for child in DATA_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)

    my_ini = "\n".join(
        [
            "[mysqld]",
            f"basedir={MYSQL_BASE}",
            f"datadir={DATA_DIR}",
            "port=3306",
            "character-set-server=utf8mb4",
            "[client]",
            "port=3306",
            "default-character-set=utf8mb4",
            "",
        ]
    )
    MY_INI.write_text(my_ini, encoding="utf-8")

    run(
        [
            str(MYSQLD),
            f"--defaults-file={MY_INI}",
            "--initialize-insecure",
            f"--basedir={MYSQL_BASE}",
            f"--datadir={DATA_DIR}",
        ]
    )


if __name__ == "__main__":
    main()
