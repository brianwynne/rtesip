"""Entry point — run with: python run.py"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=80,
        log_level="info",
    )
