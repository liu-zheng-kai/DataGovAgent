from pathlib import Path


targets = [
    Path(r"C:\ProgramData\MySQL\MySQL Server 8.4\mysqld-user.log"),
    Path(r"C:\ProgramData\MySQL\MySQL Server 8.4\Data\Zac.err"),
]

for path in targets:
    print(f"===== {path} =====")
    if not path.exists():
        print("not found")
        continue
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[-120:]:
        print(line)
