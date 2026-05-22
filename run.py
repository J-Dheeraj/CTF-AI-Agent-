"""run.py — Start the CTF Command Center server."""
import sys
import os

# Ensure the project directory is on sys.path so local modules resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
