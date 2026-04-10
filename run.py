"""Entry point — run with: python run.py"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("RTESIP_PORT", "80"))
    # PYTHONASYNCIODEBUG=1 logs slow callbacks but adds ~40% CPU on Pi 3
    # Enable temporarily for debugging only:
    # os.environ["PYTHONASYNCIODEBUG"] = "1"
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
