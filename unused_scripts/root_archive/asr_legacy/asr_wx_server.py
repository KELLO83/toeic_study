from fastapi import FastAPI
from pydantic import BaseModel
import whisperx
import torch

app = FastAPI(title="ASR-WX Service")
device = "cuda" if torch.cuda.is_available() else "cpu"

align_model = None
align_metadata = None


def get_align_model():
    global align_model, align_metadata
    if align_model is None:
        align_model, align_metadata = whisperx.load_align_model(
            language_code="en",
            device=device,
        )
    return align_model, align_metadata


class AlignSeg(BaseModel):
    text: str
    start: float
    end: float


class AlignRequest(BaseModel):
    audio_path: str
    segments: list[AlignSeg]


@app.get("/health")
def health():
    return {"status": "ok", "device": device}


@app.post("/align")
def align(req: AlignRequest):
    model, metadata = get_align_model()
    audio = whisperx.load_audio(req.audio_path)
    input_segments = [{"text": s.text, "start": s.start, "end": s.end} for s in req.segments]
    out = whisperx.align(
        input_segments,
        model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    return out
