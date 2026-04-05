import subprocess
from pathlib import Path


MYSQL = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")


def run(sql: str):
    cmd = [
        str(MYSQL),
        "-h",
        "127.0.0.1",
        "-P",
        "3306",
        "-u",
        "root",
        "-proot",
        "-e",
        sql,
    ]
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    run("DROP DATABASE IF EXISTS metadata_governance;")
    run(
        "CREATE DATABASE metadata_governance "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )
