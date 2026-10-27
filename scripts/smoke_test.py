"""启动一个临时 uvicorn 进程，验证应用能真实启动并响应 /healthz。

用途：不依赖手动开终端，快速做一次端到端冒烟检查。
运行：conda run -n test python scripts/smoke_test.py
"""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8123


def main() -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/healthz", timeout=1
                ) as response:
                    print("HTTP", response.status, response.read().decode("utf-8"))
                    return
            except Exception:
                time.sleep(0.1)
        print("服务未能启动")
    finally:
        process.terminate()
        try:
            output = process.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired:
            process.kill()
            output = process.communicate()[0]
        print("--- uvicorn 输出 ---")
        print(output)


if __name__ == "__main__":
    main()
