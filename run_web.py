"""
Start the Board Generator Studio web API server.
Run from the project root: python run_web.py
Then open the frontend (e.g. http://localhost:5173 after npm run dev in web/).
"""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
