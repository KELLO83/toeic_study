from fastapi import FastAPI
from pydantic import BaseModel
from faster_whisper import WhisperModel

app = FastAPI(title="ASR-FW Service")

# Keep model lazy-loaded to reduce startup time and avoid loading on import.
model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global model
    if model is None:
        model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    return model


class TranscribeRequest(BaseModel):
    audio_path: str
    language: str = "en"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
def transcribe(req: TranscribeRequest):
    m = get_model()
    segments, info = m.transcribe(
        req.audio_path,
        language=req.language,
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    output = []
    for s in segments:
        output.append(
            {
                "text": s.text.strip(),
                "start": float(s.start),
                "end": float(s.end),
            }
        )

    return {"duration": float(info.duration), "segments": output}
