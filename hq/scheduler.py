"""
CrossWave HQ — standalone scheduled sync runner
Usage: python scheduler.py              # one-shot sync
       python scheduler.py --watch      # continuous loop every 30min
       python scheduler.py --interval 900  # custom interval seconds
"""
import asyncio
import os
import subprocess
import sys
import time

BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))

async def run_sync():
    print(f"[scheduler] Running sync at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "from server import polsia_sync; import asyncio; asyncio.run(polsia_sync())",
        cwd=BRIDGE_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        print(stdout.decode().strip())
    if stderr:
        print(f"[scheduler] stderr: {stderr.decode().strip()}", file=sys.stderr)
    return proc.returncode == 0

async def main():
    watch = "--watch" in sys.argv or "-w" in sys.argv
    interval = 1800
    for i, arg in enumerate(sys.argv):
        if arg == "--interval" and i + 1 < len(sys.argv):
            interval = int(sys.argv[i + 1])

    ok = await run_sync()
    if not watch:
        sys.exit(0 if ok else 1)

    print(f"[scheduler] Watch mode, interval={interval}s")
    while True:
        await asyncio.sleep(interval)
        await run_sync()

if __name__ == "__main__":
    asyncio.run(main())
