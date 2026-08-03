#!/usr/bin/env python3
"""Recruiter Agency — FastAPI Server Entry Point.

Run with:
    python run_server.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )