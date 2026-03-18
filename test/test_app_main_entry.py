import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_MAIN = PROJECT_ROOT / "app" / "main.py"
SAMPLE_INPUT = PROJECT_ROOT / "module_1_2" / "data" / "P020210610345840579453.pdf"


def main() -> None:
    if not SAMPLE_INPUT.exists():
        raise FileNotFoundError(f"未找到样例合同: {SAMPLE_INPUT}")

    cmd = [
        sys.executable,
        str(APP_MAIN),
        str(SAMPLE_INPUT),
        "--no-pdf",
    ]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True)
    print("=" * 100)
    print(f"app/main.py 退出码: {result.returncode}")
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
