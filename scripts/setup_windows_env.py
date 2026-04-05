from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MYSQL_BASE = Path(r"C:\Program Files\MySQL\MySQL Server 8.4")
MYSQLD = MYSQL_BASE / "bin" / "mysqld.exe"
MYSQL = MYSQL_BASE / "bin" / "mysql.exe"
SC = Path(r"C:\Windows\System32\sc.exe")
SERVICE_NAME = "MySQL84"
MYSQL_HOME = Path(r"C:\ProgramData\MySQL\MySQL Server 8.4")
MY_INI = MYSQL_HOME / "my.ini"
DATA_DIR = MYSQL_HOME / "Data"


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        fallback = text.encode("gbk", errors="replace").decode("gbk", errors="replace")
        print(fallback)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True):
    safe_print("> " + " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.stdout.strip():
        safe_print(result.stdout.strip())
    if result.stderr.strip():
        safe_print(result.stderr.strip())
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result


def ensure_mysql_installed():
    if not MYSQLD.exists() or not MYSQL.exists():
        raise FileNotFoundError(
            f"MySQL binary not found. Expected at: {MYSQLD} and {MYSQL}"
        )


def ensure_mysql_config():
    MYSQL_HOME.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
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
    MY_INI.write_text(content, encoding="utf-8")


def clear_datadir():
    expected = Path(r"C:\ProgramData\MySQL\MySQL Server 8.4\Data")
    if DATA_DIR.resolve() != expected.resolve():
        raise RuntimeError(f"Refusing to clear unexpected datadir: {DATA_DIR}")
    for child in DATA_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def has_broken_init_artifacts() -> bool:
    # Broken bootstrap leaves core files but no mysql system schema.
    return (DATA_DIR / "ibdata1").exists() and not (DATA_DIR / "mysql").exists()


def is_mysql_initialized() -> bool:
    return any(
        [
            (DATA_DIR / "mysql").exists(),
            (DATA_DIR / "ibdata1").exists(),
            (DATA_DIR / "mysql.ibd").exists(),
        ]
    )


def ensure_mysql_initialized():
    if is_mysql_initialized():
        if has_broken_init_artifacts():
            clear_datadir()
        else:
            return
    run(
        [
            str(MYSQLD),
            f"--defaults-file={MY_INI}",
            "--initialize-insecure",
            f"--basedir={MYSQL_BASE}",
            f"--datadir={DATA_DIR}",
        ]
    )


def ensure_mysql_service():
    service_running = False
    query = run([str(SC), "query", SERVICE_NAME], check=False)
    combined = f"{query.stdout}\n{query.stderr}"
    if "FAILED 1060" in combined:
        install = run(
            [
                str(MYSQLD),
                "--install",
                SERVICE_NAME,
                f"--defaults-file={MY_INI}",
            ],
            check=False,
        )
        if install.returncode != 0:
            return False
    start = run([str(SC), "start", SERVICE_NAME], check=False)
    if start.returncode == 0 or "already running" in f"{start.stdout}{start.stderr}".lower():
        service_running = True
    return service_running


def start_mysql_user_process():
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


def wait_for_mysql_ready(timeout_seconds: int = 60):
    probes = [
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
    start = time.time()
    while time.time() - start < timeout_seconds:
        for cmd in probes:
            probe = run(cmd, check=False)
            if probe.returncode == 0:
                return
        time.sleep(2)
    raise TimeoutError("MySQL did not become ready in time.")


def run_sql(sql: str, password: str | None) -> bool:
    cmd = [str(MYSQL), "-h", "127.0.0.1", "-P", "3306", "-u", "root"]
    if password:
        cmd.append(f"-p{password}")
    cmd.extend(["-e", sql])
    result = run(cmd, check=False)
    return result.returncode == 0


def ensure_mysql_root_and_database():
    alter_sql = "ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';"
    create_db_sql = (
        "CREATE DATABASE IF NOT EXISTS metadata_governance "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )

    if run_sql(alter_sql, password=None):
        pass
    elif run_sql(alter_sql, password="root"):
        pass
    else:
        raise RuntimeError("Unable to set MySQL root password to 'root'.")

    if not run_sql(create_db_sql, password="root"):
        raise RuntimeError("Unable to create metadata_governance database.")


def ensure_project_env():
    env_example = PROJECT_ROOT / ".env.example"
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists() and env_example.exists():
        shutil.copyfile(env_example, env_file)


def ensure_python_env_and_deps():
    venv_dir = PROJECT_ROOT / ".venv"
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])

    venv_python = venv_dir / "Scripts" / "python.exe"
    run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_python), "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")])

    ensure_project_env()
    run([str(venv_python), "-m", "app.seed.seed_data"], cwd=PROJECT_ROOT)


def main():
    print("=== setup windows env start ===")
    ensure_mysql_installed()
    ensure_mysql_config()
    ensure_mysql_initialized()
    if not ensure_mysql_service():
        start_mysql_user_process()
    wait_for_mysql_ready()
    ensure_mysql_root_and_database()
    ensure_python_env_and_deps()
    print("=== setup windows env done ===")


if __name__ == "__main__":
    main()
