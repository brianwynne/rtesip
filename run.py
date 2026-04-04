"""Entry point — run with: python run.py"""

import os
import platform

import uvicorn

if __name__ == "__main__":
    default_port = "8080" if platform.system() == "Windows" else "80"
    port = int(os.environ.get("RTESIP_PORT", default_port))

    # Auto-open browser on Windows
    if platform.system() == "Windows":
        import webbrowser
        import threading
        threading.Timer(2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
