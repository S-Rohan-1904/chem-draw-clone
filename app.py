"""Hugging Face Spaces entry point (Gradio SDK).

Free Spaces only allow the Gradio/Streamlit/static SDKs, so the FastAPI app is
served here with a minimal Gradio page mounted at /gradio to satisfy the SDK.
The real UI is the built frontend served at /.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("CHEM_DB_PATH", str(ROOT / "backend" / "data.db"))
os.environ["CHEM_DEFER_FRONTEND"] = "1"  # the static mount must come after the Gradio mount

import gradio as gr  # noqa: E402
import uvicorn  # noqa: E402

from app.main import app as fastapi_app, mount_frontend  # noqa: E402

with gr.Blocks() as demo:
    gr.Markdown("The app is served at the Space root URL.")

app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")
mount_frontend(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
