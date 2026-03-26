"""
Entry point for the Board Generator Studio web executable (PyInstaller).
Starts the API server with the built frontend and optionally opens the browser.
Use run_web.py for development (reload=True); this launcher is for frozen builds (reload=False).
"""

from __future__ import annotations

import webbrowser

import uvicorn

if __name__ == "__main__":
    print("Starting Board Generator Studio at http://localhost:8000")
    print("Close this window to stop the server.")
    webbrowser.open("http://localhost:8000")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
