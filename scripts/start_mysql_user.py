import subprocess
import time
from pathlib import Path


MYSQL_BASE = Path(r"C:\Program Files\MySQL\MySQL Server 8.4")
MYSQLD = MYSQL_BASE / "bin" / "mysqld.exe"
MYSQL = MYSQL_BASE / "bin" / "mysql.exe"
MYSQL_HOME = Path(r"C:\ProgramData\MySQL\MySQL Server 8.4")
MY_INI = MYSQL_HOME / "my.ini"
DATA_DIR = MYSQL_HOME / "Data"


def start():
    log_file = MYSQL_HOME / "mysqld-user.log"
    with log_file.open("a", encoding="utf-8") as out:
        subprocess.Popen(
            [
                str(MYSQLD),
                f"--defaults-file={MY_INI}",
                f"--basedir={MYSQL_BASE}",
                f"--datadir={DATA_DIR}",
                "--port=3306",
                "--bind-address=127.0.0.1",
            ],
            stdout=out,
            stderr=out,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )


def mysql_probe_once():
    variants = [
        [str(MYSQL), "-h", "127.0.0.1", "-P", "3306", "-u", "root", "-e", "SELECT 1;"],
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
            "SELECT 1;",
        ],
    ]
    last = None
    for cmd in variants:
        last = subprocess.run(
            cmd, text=True, capture_output=True, encoding="utf-8", errors="ignore"
        )
        if last.returncode == 0:
            return True, last
    return False, last


def probe():
    for _ in range(30):
        ok, p = mysql_probe_once()
        if ok:
            print("mysql ready")
            print(p.stdout.strip())
            return True
        time.sleep(1)
    print("mysql not ready")
    print(p.stderr.strip())
    return False


if __name__ == "__main__":
    if probe():
        print("mysql already running")
        raise SystemExit(0)
    start()
    ok = probe()
    raise SystemExit(0 if ok else 1)
