from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import os
import shutil
import re
from openai import OpenAI
import requests
import json
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False
from sqlalchemy.orm import Session
from sqlalchemy import text # Import text
from database import SessionLocal, engine, get_db
import models
from datetime import datetime

app = FastAPI()

# Create Tables
models.Base.metadata.create_all(bind=engine)

# Enable CORS so Next.js (port 3000) can call FastAPI (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Config
DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "database": "toeic",
    "user": "postgres",
    "password": "1234"
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

# SQLAlchemy DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Directory for LC Audio Files
LC_UPLOAD_DIR = "uploads/lc"
os.makedirs(LC_UPLOAD_DIR, exist_ok=True)

# Whisper Model Initialization (High accuracy model)
# print("Loading Whisper Model (large-v3 on GPU)...")
# try:
#     whisper_model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
#     print("Whisper Model Loaded on GPU.")

# except Exception as e:
#     print(f"Failed to load on GPU, falling back to CPU (medium model): {e}")
#     whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")

import torch
device = "cuda" if torch.cuda.is_available() else "cpu"

# ================================
# WHISPER MODEL CONFIGURATION
# Options: "large-v3" (높은 정확도, 느림) 
#          "distil-large-v3" (빠름, 약간 낮은 정확도)
# ================================
WHISPER_MODEL = "large-v3"  # 변경하려면 여기 수정
WHISPERX_SERVICE_URL = os.getenv("WHISPERX_SERVICE_URL", "").strip()
WHISPER_FW_SERVICE_URL = os.getenv("WHISPER_FW_SERVICE_URL", "").strip()
whisper_model = None

def get_whisper_model():
    global whisper_model
    if not FASTER_WHISPER_AVAILABLE:
        raise RuntimeError("faster-whisper is not installed. Set WHISPER_FW_SERVICE_URL or install faster-whisper.")
    if whisper_model is None:
        print(f"Loading Whisper Model ({WHISPER_MODEL}) on {device}... (최초 1회만 소요)")
        whisper_model = WhisperModel(WHISPER_MODEL, device=device, compute_type="int8_float16")
        print(f"✅ Whisper Model Loaded on {device} ({WHISPER_MODEL}).")
    return whisper_model

@app.get("/")
def read_root():
    return {"message": "TOEIC Whisper Backend is running!"}

# ... (omitted parts)


# --------------------------------------------------------------------------------
# Hybrid Segmentation Logic (Text + Silence) - Global Definition
# --------------------------------------------------------------------------------
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
    print("DEBUG: static_ffmpeg paths added.")
except ImportError:
     print("WARNING: static_ffmpeg not installed. Ensure ffmpeg is in PATH.")
except Exception as e:
    print(f"WARNING: static_ffmpeg initialization failed: {e}")

from pydub import AudioSegment
from pydub.silence import detect_nonsilent

class HybridSegmenter:
    """
    4단계 파이프라인 세그멘터
    [1단계] 구조 앵커 (Part/Number/Questions) - 외부에서 처리
    [2단계] Silence Snap - 비대칭 탐색 (-1.0s ~ +0.3s)
    [3단계] 컷 보정 (start -0.2s, end +0.15s)
    [4단계] 안정성 체크 (min segment length)
    """
    
    def __init__(self, audio_path):
        self.audio = AudioSegment.from_file(audio_path)
        self.audio_length_ms = len(self.audio)
        self.avg_db = self.audio.dBFS
        # 적응형 무음 임계값: 평균 볼륨보다 16~20dB 낮으면 무음
        self.silence_threshold = self.avg_db - 18
        print(f"DEBUG: Audio Loaded. Length: {self.audio_length_ms/1000:.1f}s, Avg: {self.avg_db:.1f}dB, Silence Threshold: {self.silence_threshold:.1f}dB")

        # VAD-like non-silence regions (ms) for boundary snapping
        try:
            self.vad_segments = detect_nonsilent(
                self.audio,
                min_silence_len=400,
                silence_thresh=self.silence_threshold,
                seek_step=10,
            )
            if self.vad_segments:
                print(f"DEBUG: VAD segments detected: {len(self.vad_segments)}")
            else:
                self.vad_segments = []
                print("DEBUG: VAD segments detected: 0")
        except Exception as e:
            self.vad_segments = []
            print(f"WARNING: VAD detection failed: {e}")

    def refine_timestamp(self, anchor_start, anchor_end, 
                         start_window_before=1.0, start_window_after=0.3,
                         end_window_before=0.3, end_window_after=0.3,
                         min_silence_ms=300):
        """
        [2단계] Silence Snap + [3단계] 컷 보정
        
        Args:
            anchor_start, anchor_end: Whisper가 제공한 원본 타임스탬프
            start_window_before: 시작점 앞쪽 탐색 범위 (기본 1.0초)
            start_window_after: 시작점 뒤쪽 탐색 범위 (기본 0.3초)
            end_window_before: 끝점 앞쪽 탐색 범위 (기본 0.3초)
            end_window_after: 끝점 뒤쪽 탐색 범위 (기본 0.3초)
            min_silence_ms: 최소 무음 길이 (기본 300ms)
        """
        anchor_start_ms = int(anchor_start * 1000)
        anchor_end_ms = int(anchor_end * 1000)
        
        # === [2단계] Silence Snap ===
        # 비대칭 탐색: 시작점은 앞쪽으로 더 많이, 끝점은 균형있게
        start_search_begin = max(0, anchor_start_ms - int(start_window_before * 1000))
        start_search_end = min(self.audio_length_ms, anchor_start_ms + int(start_window_after * 1000))
        
        end_search_begin = max(0, anchor_end_ms - int(end_window_before * 1000))
        end_search_end = min(self.audio_length_ms, anchor_end_ms + int(end_window_after * 1000))
        
        # 시작점: 무음이 끝나는 지점 찾기
        snapped_start = self._find_silence_end(start_search_begin, start_search_end, 
                                                anchor_start_ms, min_silence_ms)
        # 끝점: 무음이 시작하는 지점 찾기  
        snapped_end = self._find_silence_start(end_search_begin, end_search_end,
                                                anchor_end_ms, min_silence_ms)
        
        # Fallback: SNAP 실패 시 anchor 그대로 사용
        final_start_ms = snapped_start if snapped_start is not None else anchor_start_ms
        final_end_ms = snapped_end if snapped_end is not None else anchor_end_ms
        
        # === [3단계] 컷 보정 ===
        final_start_ms = max(0, final_start_ms - 200)  # -0.2초 버퍼
        final_end_ms = min(self.audio_length_ms, final_end_ms + 150)  # +0.15초 버퍼

        # === [VAD] 경계 스냅 (가까운 무음 경계에만 적용) ===
        vad_seg = self._find_vad_segment(anchor_start_ms, anchor_end_ms)
        if vad_seg is not None:
            vad_start_ms, vad_end_ms = vad_seg
            vad_duration_s = (vad_end_ms - vad_start_ms) / 1000.0
            if vad_duration_s <= 12.0:
                vad_snap_ms = 400
                if abs(final_start_ms - vad_start_ms) <= vad_snap_ms:
                    final_start_ms = vad_start_ms
                if abs(final_end_ms - vad_end_ms) <= vad_snap_ms:
                    final_end_ms = vad_end_ms
                # Do not cross VAD boundary
                final_start_ms = max(final_start_ms, vad_start_ms)
                final_end_ms = min(final_end_ms, vad_end_ms)
        
        # 변환: ms -> seconds
        final_start = final_start_ms / 1000.0
        final_end = final_end_ms / 1000.0
        
        # 디버그 로그
        snap_status = []
        if snapped_start is not None:
            snap_status.append(f"S:{anchor_start:.2f}->{final_start:.2f}")
        if snapped_end is not None:
            snap_status.append(f"E:{anchor_end:.2f}->{final_end:.2f}")
        
        # SNAP debug log intentionally disabled (too noisy).
        
        return final_start, final_end

    def _find_silence_end(self, search_start_ms, search_end_ms, target_ms, min_silence_ms, chunk_size=30):
        """무음 구간이 끝나는 지점 (= 음성 시작 직전) 찾기"""
        segment = self.audio[search_start_ms:search_end_ms]
        if len(segment) == 0:
            return None
            
        silence_regions = []  # [(start_ms, end_ms), ...]
        in_silence = False
        silence_start = 0
        
        for i in range(0, len(segment), chunk_size):
            chunk = segment[i:i+chunk_size]
            is_silent = chunk.dBFS < self.silence_threshold
            
            if is_silent and not in_silence:
                # 무음 시작
                in_silence = True
                silence_start = i
            elif not is_silent and in_silence:
                # 무음 끝
                in_silence = False
                silence_length = i - silence_start
                if silence_length >= min_silence_ms:
                    # 무음의 끝점 (= 음성 시작) 저장
                    silence_regions.append(search_start_ms + i)
        
        if not silence_regions:
            return None
        
        # target에 가장 가까운 무음 끝점 반환
        return min(silence_regions, key=lambda x: abs(x - target_ms))

    def _find_silence_start(self, search_start_ms, search_end_ms, target_ms, min_silence_ms, chunk_size=30):
        """무음 구간이 시작하는 지점 (= 음성 끝 직후) 찾기"""
        segment = self.audio[search_start_ms:search_end_ms]
        if len(segment) == 0:
            return None
            
        silence_regions = []
        in_silence = False
        silence_start = 0
        
        for i in range(0, len(segment), chunk_size):
            chunk = segment[i:i+chunk_size]
            is_silent = chunk.dBFS < self.silence_threshold
            
            if is_silent and not in_silence:
                # 무음 시작
                in_silence = True
                silence_start = i
            elif not is_silent and in_silence:
                # 무음 끝
                in_silence = False
                silence_length = i - silence_start
                if silence_length >= min_silence_ms:
                    # 무음의 시작점 저장
                    silence_regions.append(search_start_ms + silence_start)
        
        # 끝까지 무음이면 마지막 구간도 추가
        if in_silence:
            silence_length = len(segment) - silence_start
            if silence_length >= min_silence_ms:
                silence_regions.append(search_start_ms + silence_start)
        
        if not silence_regions:
            return None
        
        # target에 가장 가까운 무음 시작점 반환
        return min(silence_regions, key=lambda x: abs(x - target_ms))

    def _find_vad_segment(self, anchor_start_ms, anchor_end_ms):
        """anchor와 가장 많이 겹치는 VAD 구간 선택"""
        if not self.vad_segments:
            return None
        best = None
        best_overlap = 0
        for seg_start, seg_end in self.vad_segments:
            overlap = max(0, min(anchor_end_ms, seg_end) - max(anchor_start_ms, seg_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best = (seg_start, seg_end)
        return best
    
    def check_segment_validity(self, start, end, min_duration=0.5):
        """[4단계] 안정성 체크: 세그먼트가 너무 짧으면 False"""
        duration = end - start
        if duration < min_duration:
            print(f"DEBUG: Segment too short ({duration:.2f}s < {min_duration}s), needs merge")
            return False
        return True

# ===================================================
# 세그먼트 후처리 함수들 (Split / Merge)
# ===================================================

def split_segment_by_question(text, start, end):
    """
    "Number X. [질문]? [대화]" 패턴을 분리
    Returns: List of (text, start, end) tuples
    """
    import re
    
    # 패턴: "Number X. [질문내용]?" 이후에 추가 텍스트가 있으면 분리
    pattern = r'((?:Number|Question)\s*\d+\.?\s*[^?]+\?)\s*(.+)'
    match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        question_part = match.group(1).strip()
        dialogue_part = match.group(2).strip()
        
        if dialogue_part:  # 대화 부분이 있으면 분리
            total_len = len(question_part) + len(dialogue_part)
            question_ratio = len(question_part) / total_len
            
            # 타임스탬프 비례 배분
            duration = end - start
            split_point = start + (duration * question_ratio)
            
            print(f"DEBUG: SPLIT! '{question_part[:30]}...' | '{dialogue_part[:30]}...'")
            return [
                (question_part, start, split_point),
                (dialogue_part, split_point, end)
            ]
    
    # 분리 불필요
    return [(text, start, end)]


def should_merge_with_next(text):
    """
    A/B/C/D 단독 패턴인지 확인
    """
    import re
    # "A." "B." "C." "D." 단독 or 매우 짧은 경우
    return bool(re.match(r'^[A-D]\.\s*$', text.strip()))


def merge_segments(segments):
    """
    A/B/C/D 패턴을 다음 세그먼트와 병합
    Input: List of (text, start, end) tuples
    Output: List of merged (text, start, end) tuples
    """
    if not segments:
        return segments
    
    merged = []
    i = 0
    
    while i < len(segments):
        text, start, end = segments[i]
        
        # A/B/C/D 단독이고 다음 세그먼트가 있으면 병합
        if should_merge_with_next(text) and i + 1 < len(segments):
            next_text, _, next_end = segments[i + 1]
            merged_text = f"{text.strip()} {next_text.strip()}"
            merged.append((merged_text, start, next_end))
            print(f"DEBUG: MERGE! '{text.strip()}' + '{next_text[:20]}...' -> '{merged_text[:30]}...'")
            i += 2  # Skip next segment
        else:
            merged.append((text, start, end))
            i += 1
    
    return merged

from fastapi import Depends

@app.get("/words")
def get_words(limit: int | None = None, db: Session = Depends(get_db)):
    try:
        query = db.query(models.ToeicWord).order_by(models.ToeicWord.id.asc())
        if limit is not None:
            query = query.limit(limit)
        words = query.all()
        return words
    except Exception as e:
        print(f"Error fetching words: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ... (existing imports)
import requests
import json
import edge_tts
from fastapi.responses import StreamingResponse
import io

# ... (existing helper functions)

# TTS Endpoint
@app.get("/tts")
async def text_to_speech(text: str, voice: str = "en-US-ChristopherNeural"):
    """
    Stream TTS audio directly without saving to file.
    Voices:
    - US: en-US-ChristopherNeural (Male), en-US-AnaNeural (Female)
    - UK: en-GB-SoniaNeural (Female), en-GB-RyanNeural (Male)
    - AU: en-AU-NatashaNeural (Female)
    """
    communicate = edge_tts.Communicate(text, voice)
    
    # Create a generator that yields chunks of audio
    async def audio_generator():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")

def validate_with_llm(word: str, meaning: str):
    url = "http://localhost:11434/api/chat"
    
    # System Prompt for Exaone 3.5 (Korean Optimized)
    system_prompt = """당신은 유능한 영어 단어 선생님입니다.
    사용자가 입력한 'Word'와 'Meaning'을 처리하세요.

    [규칙]
    1. **Meaning이 비어있는 경우**:
       - Word의 오타를 수정하세요.
       - Meaning에는 **오직 한국어 뜻만** 1~2개 입력하세요. (영어 예시, 괄호 설명 절대 금지)
       - 예: "publicize" -> "알리다, 홍보하다" (O) / "알리다 (announce)" (X)
       - 상태는 'FIX'를 반환하세요.
    
    2. **Meaning이 입력된 경우 (검증 모드)**:
       - Word의 오타를 잡으세요.
       - Meaning이 Word의 뜻으로 적절하다면(지엽적이라도 맞으면) 'OK'를 반환하세요.
       - 틀렸다면 'FIX'를 반환하고 수정하세요.

    [출력 결과]
    반드시 아래 JSON 형식으로만 응답하세요:
    {
        "status": "OK" 또는 "FIX",
        "corrected_word": "수정된 단어 (수정 없으면 null)",
        "corrected_meaning": "채워진/수정된 뜻 (수정 없으면 null)",
        "message": "짧은 설명"
    }
    """
    
    user_content = f"Word: {word}\nMeaning: {meaning}"
    
    payload = {
        "model": "exaone3.5", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "format": "json",
        "stream": False,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return json.loads(response.json()['message']['content'])
        return {"status": "ERROR", "message": "LLM Connection Failed"}
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"status": "ERROR", "message": str(e)}

# Load API Key from secrets.json
SOLAR_API_KEY = ""
try:
    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        SOLAR_API_KEY = secrets.get("SOLAR_API_KEY", "")
except Exception as e:
    print(f"Warning: Could not load secrets.json: {e}")

def validate_with_solar_pro(word: str, meaning: str):
    if not SOLAR_API_KEY or "YOUR_ACTUAL_API_KEY" in SOLAR_API_KEY:
        return {"status": "ERROR", "message": "Backend Error: Add your API Key to secrets.json"}

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=SOLAR_API_KEY
    )
    
    system_prompt = """당신은 유능한 영어 단어 선생님입니다.
    사용자가 입력한 'Word'와 'Meaning'을 처리하세요.

    [규칙]
    1. **Meaning이 비어있는 경우**:
       - Word의 오타를 수정하세요.
       - Meaning에는 **오직 한국어 뜻만** 1~2개 입력하세요. (영어 예시, 괄호 설명 절대 금지)
       - 예: "publicize" -> "알리다, 홍보하다" (O)
       - 상태는 'FIX'를 반환하세요.
    
    2. **Meaning이 입력된 경우 (검증 모드)**:
       - Word의 오타를 잡으세요.
       - Meaning이 Word의 뜻으로 적절하다면 'OK'를 반환하세요.
       - 틀렸다면 'FIX'를 반환하고 수정하세요.

    [출력 결과]
    반드시 아래 JSON 형식으로만 응답하세요:
    {
        "status": "OK" 또는 "FIX",
        "corrected_word": "수정된 단어 (수정 없으면 null)",
        "corrected_meaning": "채워진/수정된 뜻 (수정 없으면 null)",
        "message": "짧은 설명"
    }
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Word: {word}\nMeaning: {meaning}"}
    ]

    try:
        # First API Call to generate reasoning (although we don't strictly use it for JSON parsing, sticking to user request style)
        response = client.chat.completions.create(
            model="upstage/solar-pro-3:free",
            messages=messages,
            extra_body={"reasoning": {"enabled": True}}
        )
        
        content = response.choices[0].message.content
        
        # Parse JSON from content (Handle potential markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
             content = content.split("```")[1].split("```")[0].strip()
            
        return json.loads(content)

    except Exception as e:
        print(f"Solar Pro Error: {e}")
        return {"status": "ERROR", "message": f"Solar Pro Error: {str(e)}"}

class AddWordRequest(BaseModel):
    word: str
    meaning: str
    confirmed: bool = False
    model_type: str = "solar-pro"  # "exaone" or "solar-pro"

class ChatRequest(BaseModel):
    message: str
    history: list = []

@app.post("/chat")
async def chat_with_solar(req: ChatRequest):
    if not SOLAR_API_KEY or "YOUR_ACTUAL_API_KEY" in SOLAR_API_KEY:
        raise HTTPException(status_code=500, detail="Backend Error: Add your API Key to secrets.json")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=SOLAR_API_KEY
    )

    messages = [
        {
            "role": "system", 
            "content": "당신은 TOEIC Whisper의 전담 AI 튜터 'Solar'입니다. 현재 채팅창은 마크다운(#, * 등)을 지원하지 않으므로, 이모지와 줄바꿈만을 이용해 가독성 있게 답변하세요. 1. [핵심 요약]을 이모지 📌와 함께 한 줄로 간단히 적고 줄을 바꾸세요. 2. 주요 내용은 💡 이모지와 함께 번호를 매겨 최대 3개까지만 짧게 설명하세요. 3. 예문은 📝 이모지와 함께 영어 문장 - 한글 해석 순으로 적으세요. 4. 각 섹션 사이에는 빈 줄을 넣어 간격을 넓게 벌리세요. 5. 마크다운 기호(##, **, >, - 등)는 절대 사용하지 마세요."
        }
    ]
    # Add history
    for msg in req.history:
        messages.append(msg)
    # Add new message
    messages.append({"role": "user", "content": req.message})

    try:
        response = client.chat.completions.create(
            model="upstage/solar-pro-3:free",
            messages=messages,
            extra_body={"reasoning": {"enabled": True}}
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        print(f"Chat Error Detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

@app.post("/words")
def add_word(req: AddWordRequest):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Duplicate Check
        cur.execute("SELECT id, meaning FROM toeic_word WHERE word = %s", (req.word,))
        existing_word = cur.fetchone()
        if existing_word:
            return {"status": "DUPLICATE", "message": f"'{req.word}'는 이미 단어장에 있습니다.\n(뜻: {existing_word['meaning']})"}

        # 2. Logic Branch
        if not req.confirmed:
            if req.model_type == "solar-pro":
                # Now using server-side key
                llm_result = validate_with_solar_pro(req.word, req.meaning)
            else:
                 # Default to Local Exaone
                 llm_result = validate_with_llm(req.word, req.meaning)
            
            # Case A: AI suggests fix
            if llm_result.get("status") == "FIX":
                return {
                    "status": "SUGGESTION",
                    "original": req,
                    "suggestion": llm_result
                }
            
            # Case B: AI says OK -> Ask user to confirm
            if llm_result.get("status") == "OK":
                 return {
                    "status": "CONFIRM_NEEDED", 
                    "message": "AI 검증 통과! 완벽한 단어입니다. (더블 체크)",
                    "original": req
                 }
                 
            return {"status": "ERROR", "message": llm_result.get("message", "AI 검증 오류")}

        # 3. If confirmed=True, INSERT
        cur.execute(
            "INSERT INTO toeic_word (word, meaning, sheet_name) VALUES (%s, %s, %s) RETURNING id",
            (req.word, req.meaning, "User Added")
        )
        new_id = cur.fetchone()['id']
        conn.commit()
        return {"status": "SUCCESS", "id": new_id, "message": "단어가 추가되었습니다!"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cur: cur.close()
        if conn: conn.close()

import pandas as pd
import io

@app.post("/words/upload")
async def upload_words_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
         raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are allowed.")
         
    try:
        # Read the uploaded file into pandas
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # We assume the columns are named '단어' and '의미' or we take first two columns
        if '단어' in df.columns and '의미' in df.columns:
            word_col = '단어'
            meaning_col = '의미'
        else:
            if len(df.columns) < 2:
                raise HTTPException(status_code=400, detail="Excel file must contain at least two columns.")
            word_col = df.columns[0]
            meaning_col = df.columns[1]

        # Extract rows and normalize obvious spreadsheet noise
        normalized_df = df[[word_col, meaning_col]].copy()
        normalized_df[word_col] = normalized_df[word_col].astype(str).str.strip()
        normalized_df[meaning_col] = normalized_df[meaning_col].astype(str).str.strip()
        normalized_df = normalized_df[
            normalized_df[word_col].ne("")
            & normalized_df[meaning_col].ne("")
            & normalized_df[word_col].ne("nan")
            & normalized_df[meaning_col].ne("nan")
        ]
        words_data = normalized_df.to_dict('records')
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")
    
    try:
        # 1. Delete all existing words and reset identity
        db.execute(text("TRUNCATE TABLE toeic_word RESTART IDENTITY CASCADE"))

        # 2. Insert new words
        inserted_words = []
        for row in words_data:
            word = str(row[word_col]).strip()
            meaning = str(row[meaning_col]).strip()
            
            if word and meaning:
                inserted_words.append(
                    models.ToeicWord(word=word, meaning=meaning, sheet_name="Excel Upload")
                )

        db.add_all(inserted_words)
        db.commit()
        return {
            "status": "SUCCESS",
            "inserted_count": len(inserted_words),
            "message": f"기존 단어가 삭제되고 새 단어 {len(inserted_words)}개가 추가되었습니다!",
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- LC (Listening Comprehension) Endpoints ---

@app.post("/lc/upload")
async def upload_lc_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # 1. Save File
    file_path = os.path.join(LC_UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Save Initial DB Record
    db = SessionLocal()
    db_audio = models.ToeicAudioFile(filename=file.filename, saved_path=file_path, status="processing")
    db.add(db_audio)
    db.commit()
    db.refresh(db_audio)
    audio_id = db_audio.id
    db.close()

    # 3. Add Background Task for Transcription
    background_tasks.add_task(process_lc_transcription, audio_id, file_path)

    return {"status": "SUCCESS", "audio_id": audio_id, "message": "파일 업로드 완료. 트랜스크립션이 배경에서 시작되었습니다."}

def process_lc_transcription(audio_id: int, file_path: str):
    print(f"DEBUG: Starting transcription for Audio ID {audio_id}, Path: {file_path}")
    db = SessionLocal()
    try:
        db_audio = db.query(models.ToeicAudioFile).filter(models.ToeicAudioFile.id == audio_id).first()
        if not db_audio:
            print(f"ERROR: Audio file {audio_id} not found in DB execution thread.")
            return

        # 1. Transcribe (FW service -> local fallback)
        raw_segments = []
        segments_generator = None
        total_duration = 0.0

        if WHISPER_FW_SERVICE_URL:
            try:
                fw_audio_path = file_path.replace("\\", "/")
                if fw_audio_path.startswith("uploads/"):
                    fw_audio_path = "/app/" + fw_audio_path
                print(f"DEBUG: Calling faster-whisper service: {WHISPER_FW_SERVICE_URL}")
                fw_res = requests.post(
                    f"{WHISPER_FW_SERVICE_URL}/transcribe",
                    json={"audio_path": fw_audio_path, "language": "en"},
                    timeout=1800,
                )
                fw_res.raise_for_status()
                fw_data = fw_res.json()
                total_duration = float(fw_data.get("duration", 0.0))
                for seg in fw_data.get("segments", []):
                    text = (seg.get("text") or "").strip()
                    if text:
                        raw_segments.append((text, float(seg.get("start", 0)), float(seg.get("end", 0))))
                print(f"DEBUG: FW service transcription completed. Segments: {len(raw_segments)}")
            except Exception as fw_err:
                print(f"WARNING: FW service failed: {fw_err}. Falling back to local faster-whisper.")

        if not raw_segments:
            print("DEBUG: Calling Whisper transcribe with optimized settings...")
            model = get_whisper_model()
            segments_generator, info = model.transcribe(
                file_path,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                word_timestamps=True,
                language="en",
                condition_on_previous_text=False,
            )
            total_duration = info.duration
            print(f"DEBUG: Transcription started. Total Duration: {total_duration}s")
        
        # [1단계] HybridSegmenter 초기화 (4단계 파이프라인)
        segmenter = None
        try:
            segmenter = HybridSegmenter(file_path)
            print("DEBUG: HybridSegmenter (4-step pipeline) initialized successfully.")
        except Exception as e:
            print(f"WARNING: Failed to load HybridSegmenter ({e}). Using raw timestamps.")

        # ===================================================
        # [새로운 방식] 세그먼트 수집 → Split → Merge → 처리
        # ===================================================
        print("DEBUG: Collecting segments from Whisper...")
        if segments_generator is not None:
            for segment in segments_generator:
                text = segment.text.strip()
                if not text:
                    continue
                if hasattr(segment, 'words') and segment.words:
                    anchor_start = float(segment.words[0].start)
                    anchor_end = float(segment.words[-1].end)
                else:
                    anchor_start = float(segment.start)
                    anchor_end = float(segment.end)
                raw_segments.append((text, anchor_start, anchor_end))
        
        print(f"[STEP 1/5] Whisper 세그먼트 수집 완료: {len(raw_segments)}개")

        if WHISPERX_SERVICE_URL and len(raw_segments) > 0:
            print(f"[STEP 2/5] WhisperX service alignment 시도 중...")
            # [FIX #3] 원본 세그먼트를 인덱스 기반 리스트로 저장 (동일 텍스트 덮어쓰기 방지)
            original_segments = [(seg[0].strip(), seg[1], seg[2]) for seg in raw_segments]
            
            try:
                wx_audio_path = file_path.replace("\\", "/")
                if wx_audio_path.startswith("uploads/"):
                    wx_audio_path = "/app/" + wx_audio_path
                wx_payload = {
                    "audio_path": wx_audio_path,
                    "segments": [{"text": t, "start": s, "end": e} for t, s, e in raw_segments],
                }
                wx_res = requests.post(f"{WHISPERX_SERVICE_URL}/align", json=wx_payload, timeout=1800)
                wx_res.raise_for_status()
                wx_data = wx_res.json()
                aligned_segments = wx_data.get("segments", [])
                
                if aligned_segments:
                    # ==========================================
                    # 5단계 정제 파이프라인 (WhisperX 결과 검증)
                    # ==========================================
                    MIN_DURATION = 0.5
                    refined_segments = []
                    prev_end = 0.0
                    prev_start = -999.0
                    prev_end_check = -999.0
                    fallback_count = 0
                    
                    for seg_idx, seg in enumerate(aligned_segments):
                        text = (seg.get("text") or "").strip()
                        if not text:
                            continue
                        
                        # [FIX #3] 원본 타임스탬프 - 인덱스 기반으로 조회
                        if seg_idx < len(original_segments):
                            orig_text, orig_start, orig_end = original_segments[seg_idx]
                        else:
                            orig_start, orig_end = seg.get("start", 0), seg.get("end", 0)
                        
                        # ========================================
                        # STEP 1: 유효 단어 필터링 (None, 역전 제거)
                        # ========================================
                        words = seg.get("words", [])
                        valid_words = [
                            w for w in words
                            if w.get("start") is not None
                            and w.get("end") is not None
                            and w["end"] > w["start"]
                        ]
                        
                        # ========================================
                        # STEP 2: 세그먼트 start/end 계산
                        # ========================================
                        fallback = False
                        fallback_reason = None
                        
                        if len(valid_words) >= 2:
                            start = valid_words[0]["start"]
                            end = valid_words[-1]["end"]
                        elif len(valid_words) == 1:
                            start, end = orig_start, orig_end
                            fallback = True
                            fallback_reason = "single_valid_word"
                        else:
                            start, end = orig_start, orig_end
                            fallback = True
                            fallback_reason = "no_valid_words"
                        
                        # ========================================
                        # STEP 3: 절대 조건 검증
                        # ========================================
                        if end <= start:
                            start, end = orig_start, orig_end
                            fallback = True
                            fallback_reason = "end_before_start"
                        
                        if (end - start) < MIN_DURATION:
                            start, end = orig_start, orig_end
                            fallback = True
                            fallback_reason = "short_duration"
                        
                        # ========================================
                        # STEP 4: Monotonic 강제 (non-overlap)
                        # ========================================
                        if start < prev_end:
                            start = prev_end + 0.02
                        if (end - start) < MIN_DURATION:
                            end = start + MIN_DURATION
                        
                        # ========================================
                        # STEP 5: 중복 저장 방지
                        # ========================================
                        if abs(start - prev_start) < 0.1 and abs(end - prev_end_check) < 0.1:
                            start, end = orig_start, orig_end
                            fallback = True
                            fallback_reason = "duplicate_range"
                            if start < prev_end:
                                start = prev_end + 0.02
                                end = max(end, start + MIN_DURATION)
                        
                        # [FIX #2] 동일 텍스트 연속 세그먼트 병합 (매우 엄격한 조건)
                        # 이전과 같은 텍스트 AND 0.1초 이내 AND 짧은 duration이면 중복으로 스킵
                        if refined_segments:
                            prev_text, prev_s, prev_e = refined_segments[-1]
                            # 완전 동일 텍스트 + 매우 근접(0.1초) + 짧은 segment(0.6초 미만)
                            if (text == prev_text and 
                                abs(start - prev_e) < 0.1 and 
                                (end - start) < 0.6):
                                continue
                        
                        refined_segments.append((text, float(start), float(end)))
                        prev_start = start
                        prev_end_check = end
                        prev_end = end
                        
                        if fallback:
                            fallback_count += 1
                    
                    raw_segments = refined_segments
                    print(f"✅ WhisperX alignment 성공! {len(raw_segments)}개 세그먼트 (fallback: {fallback_count}개)")
                else:
                    print("WARNING: WhisperX service returned empty segments. Using original timestamps.")
            except Exception as wx_err:
                print(f"WARNING: WhisperX service failed: {wx_err}. Using original timestamps.")

        
        # [Split 단계] "Number X. 질문? 대화" 분리
        split_segments = []
        for text, start, end in raw_segments:
            split_result = split_segment_by_question(text, start, end)
            split_segments.extend(split_result)
        
        print(f"DEBUG: After split: {len(split_segments)} segments")
        
        # [Merge 단계] A/B/C/D 병합
        merged_segments = merge_segments(split_segments)
        print(f"DEBUG: After merge: {len(merged_segments)} segments")
        
        # 최종 처리용 변수들
        current_question = None
        current_part = 0
        last_progress_update = 0
        pending_context = []
        active_set_info = None
        processed_segments = 0
        
        print("DEBUG: Starting final processing loop...")
        for text, anchor_start, anchor_end in merged_segments:
            processed_segments += 1
            
            # [2-3단계] Silence Snap + 컷 보정
            if segmenter:
                try:
                    start, end = segmenter.refine_timestamp(anchor_start, anchor_end)
                    
                    # [4단계] 안정성 체크
                    if not segmenter.check_segment_validity(start, end):
                        start = max(0, anchor_start - 0.2)
                        end = anchor_end + 0.15
                except Exception as seg_err:
                    print(f"Warning: Segmentation error for '{text[:30]}...': {seg_err}")
                    start = max(0, anchor_start - 0.2)
                    end = anchor_end + 0.15
            else:
                start = max(0, anchor_start - 0.2)
                end = anchor_end + 0.15
            # -------------------------
            
            # Progress Update
            if total_duration > 0:
                progress = int((end / total_duration) * 100)
                # Force update if progress changed significantly or it's the first segment
                if progress > last_progress_update or processed_segments == 1: 
                    print(f"Progress: {progress}% (Segment: {processed_segments})")
                    db_audio.progress = progress
                    db.commit() 
                    last_progress_update = progress

            # 2. Part Detection Logic
            part_match = re.search(r"Part\s*(\d+)", text, re.IGNORECASE)
            if part_match:
                current_part = int(part_match.group(1))
                print(f"Detected Part: {current_part}")
                pending_context = [] 
                active_set_info = None
                current_question = None

            # 3. Question Parsing Logic
            
            # 3-1. Detect Question Set (e.g., "Questions 32 through 34 refer to..." or "Number 32 through 34 refer to...")
            set_match = re.search(r"(Questions?|Number)\s*(\d+)\s*(through|and|-|to)\s*(\d+)", text, re.IGNORECASE)

            
            # 3-2. Detect Individual Question Start (e.g., "Number 1.", "Question 1")
            # [FIX] 문장 시작만 인식 - set 안내문 안의 숫자 제외
            q_match = re.match(r"^\s*Number\s*(\d+)\b", text, re.IGNORECASE)
            
            if set_match:
                # Start of a new set.
                current_question = None 
                
                # [FIX 2] 새 set 시작 시 이전 pending_context 초기화
                pending_context = []
                
                start_q = int(set_match.group(2))
                end_q = int(set_match.group(4))

                # Initialize new set info
                active_set_info = {
                    "start": start_q,
                    "end": end_q,
                    "context_transcripts": [],
                    "context_saved": False  # [FIX 1] 중복 할당 방지 플래그
                }
                
                # The instruction itself is part of the context
                transcript_obj = {"start": start, "end": end, "text": text}
                pending_context.append(transcript_obj)
                
                # Also save to active set context for later questions
                active_set_info["context_transcripts"].append(transcript_obj)

                # retroactively update set_number for questions that might have been created before this header
                try:
                    existing_questions_in_range = db.query(models.ToeicQuestion).filter(
                        models.ToeicQuestion.audio_id == audio_id,
                        models.ToeicQuestion.question_number >= start_q,
                        models.ToeicQuestion.question_number <= end_q
                    ).all()
                    
                    for eq in existing_questions_in_range:
                        if eq.set_number is None:
                             eq.set_number = start_q
                             print(f"Retroactively updated Q{eq.question_number} to Set {start_q}")
                    db.flush()
                except Exception as e:
                    print(f"Error retroactively updating set numbers: {e}")

            # [FIX #1] 독립 처리: q_match는 항상 체크 (set_match와 별도)
            # 같은 세그먼트에 "Questions X through Y" + "Number X"가 있으면 둘 다 처리
            if q_match:
                q_val = int(q_match.group(1))  # group(1)로 변경 (정규식 수정됨)
                
                # [FIX v2-2] Number X = 절대 경계 (이전 question 즉시 종료)
                # 새 question 시작 = 이전 question 완전 종료
                previous_question = current_question
                current_question = None
                
                # Determine set number
                current_set_num = None
                if active_set_info and active_set_info["start"] <= q_val <= active_set_info["end"]:
                    current_set_num = active_set_info["start"]
                else:
                    # [FIX 2] set 범위 벗어나면 pending_context도 초기화
                    active_set_info = None
                    pending_context = []


                # Create or find question
                existing_q = db.query(models.ToeicQuestion).filter(
                    models.ToeicQuestion.audio_id == audio_id,
                    models.ToeicQuestion.question_number == q_val
                ).first()

                if existing_q:
                    current_question = existing_q
                    current_question.end_time = end 
                else:
                    current_question = models.ToeicQuestion(
                        audio_id=audio_id,
                        question_number=q_val,
                        part=current_part,
                        set_number=current_set_num,
                        start_time=start,
                        end_time=end
                    )
                    db.add(current_question)
                    db.flush()
                
                # Attach Context (Conversation) - Pending
                if pending_context:
                    for ctx in pending_context:
                        db_transcript = models.ToeicTranscript(
                            question_id=current_question.id,
                            start_time=ctx["start"],
                            end_time=ctx["end"],
                            text=ctx["text"],
                            label="conversation"
                        )
                        db.add(db_transcript)
                        if ctx["start"] < current_question.start_time:
                            current_question.start_time = ctx["start"]
                    pending_context = []
                
                # [FIX 1] Attach Context - Inherited from Set (첫 번째 question만!)
                elif active_set_info and active_set_info["context_transcripts"]:
                    if not active_set_info.get("context_saved", False):
                        # set 첫 번째 question에만 context 저장
                        for ctx in active_set_info["context_transcripts"]:
                            db_transcript = models.ToeicTranscript(
                                question_id=current_question.id,
                                start_time=ctx["start"],
                                end_time=ctx["end"],
                                text=ctx["text"],
                                label="conversation"
                            )
                            db.add(db_transcript)
                            if ctx["start"] < current_question.start_time:
                                current_question.start_time = ctx["start"]
                        active_set_info["context_saved"] = True  # 중복 방지
                
                # Finally, add the Question Text itself ("Number X...")
                db_transcript = models.ToeicTranscript(
                    question_id=current_question.id,
                    start_time=start,
                    end_time=end,
                    text=text,
                    label="question"
                )
                db.add(db_transcript)

            else:
                # Normal text segment
                transcript_obj = {"start": start, "end": end, "text": text}
                
                if current_question:
                    # Attached to current question
                    current_question.end_time = end
                    db_transcript = models.ToeicTranscript(
                        question_id=current_question.id,
                        start_time=start,
                        end_time=end,
                        text=text,
                        label="conversation" # Normal text attached to question is usually conversation continuing? No, usually questions are at the End.
                        # Wait, after "Number 4...", usually it's silent or next question. 
                        # But sometimes "Number 4" is short, and description follows?
                        # User said "Number 1 ... What does the man ask..." is all question.
                        # So if we are INSIDE a question, subsequent text is likely Question content too?
                        # Actually standard TOEIC: Conversation -> "Number 4" -> (Silence) -> "Number 5".
                        # So text appearing AFTER "Number X" is Question Content.
                    )
                    # Let's enforce: If it's attached to a specific question (and it's not the initial conversation context), it's likely the question text itself.
                    
                    # Logic: 
                    # Part 1 & 2: Text following "Number X" is the script/options -> label="conversation"
                    # Part 3 & 4: Text following "Number X" is the question text itself -> label="question"
                    if current_part in [1, 2]:
                        db_transcript.label = "conversation"
                    else:
                        db_transcript.label = "question"
                    
                    db.add(db_transcript)
                else:
                    # Context appearing before a question
                    pending_context.append(transcript_obj)
                    if active_set_info:
                        active_set_info["context_transcripts"].append(transcript_obj)

            # 4. Add to Transcripts -> Moved inside logical blocks above
            
        # [FIX 4] DB commit 전 시간 순서 검증 (겹침 수정)
        print(f"[STEP 5/5] 시간 순서 검증 및 겹침 수정 중...")
        try:
            all_questions = db.query(models.ToeicQuestion).filter(
                models.ToeicQuestion.audio_id == audio_id
            ).all()
            
            fixed_count = 0
            dedup_count = 0
            
            # [FIX] Cross-question 중복 제거: audio_id 전체 단위로 seen 관리
            seen_global = set()  # (text, rounded_start, rounded_end) - 전역
            
            for q in all_questions:
                transcripts = db.query(models.ToeicTranscript).filter(
                    models.ToeicTranscript.question_id == q.id
                ).order_by(models.ToeicTranscript.start_time).all()
                
                to_delete = []
                
                prev_end = 0.0
                for t in transcripts:
                    # 시간 겹침 수정
                    if t.start_time < prev_end:
                        t.start_time = prev_end + 0.02
                        fixed_count += 1
                    if t.end_time <= t.start_time:
                        t.end_time = t.start_time + 0.5
                        fixed_count += 1
                    
                    # [FIX] Cross-question 중복 체크: audio_id 전체 단위
                    dedup_key = (t.text.strip(), round(t.start_time, 1), round(t.end_time, 1))
                    if dedup_key in seen_global:
                        to_delete.append(t)
                        dedup_count += 1
                    else:
                        seen_global.add(dedup_key)
                        prev_end = t.end_time
                
                # 중복 삭제
                for t in to_delete:
                    db.delete(t)
            
            if fixed_count > 0:
                print(f"✅ 시간 겹침 {fixed_count}건 수정됨")
            if dedup_count > 0:
                print(f"✅ Cross-question 중복 {dedup_count}건 제거됨")
            db.flush()
        except Exception as fix_err:
            print(f"Warning: 시간 순서 검증 중 오류: {fix_err}")
            
            
        db_audio.status = "completed"
        db_audio.progress = 100
        db.commit()
        print(f"Transcription completed for audio ID {audio_id}")

    except Exception as e:
        print(f"Transcription Error: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            if 'db_audio' in locals() and db_audio:
                db_audio.status = "error"
                db.commit()
        except Exception as  db_err:
             print(f"Failed to update DB status to error: {db_err}")

    finally:
        db.close()

@app.get("/lc/files")
def list_lc_files():
    db = SessionLocal()
    files = db.query(models.ToeicAudioFile).order_by(models.ToeicAudioFile.upload_date.desc()).all()
    db.close()
    return files

@app.get("/lc/data/{audio_id}")
def get_lc_data(audio_id: int):
    db = SessionLocal()
    questions = db.query(models.ToeicQuestion).filter(models.ToeicQuestion.audio_id == audio_id).order_by(models.ToeicQuestion.question_number).all()
    
    result = []
    for q in questions:
        transcripts = db.query(models.ToeicTranscript).filter(models.ToeicTranscript.question_id == q.id).order_by(models.ToeicTranscript.start_time).all()
        result.append({
            "id": q.id,
            "question_number": q.question_number,
            "part": q.part,  # Added part field
            "set_number": q.set_number, # Added set_number
            "start_time": q.start_time,
            "end_time": q.end_time,
            "transcripts": [
                {"start_time": t.start_time, "end_time": t.end_time, "text": t.text, "label": t.label} for t in transcripts
            ]
        })
    db.close()
    return result

@app.get("/lc/audio/{audio_id}")
def serve_lc_audio(audio_id: int):
    db = SessionLocal()
    db_audio = db.query(models.ToeicAudioFile).filter(models.ToeicAudioFile.id == audio_id).first()
    db.close()
    
    if not db_audio or not os.path.exists(db_audio.saved_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(db_audio.saved_path, media_type="audio/mpeg")

@app.delete("/lc/files/{file_id}")
def delete_lc_file(file_id: int):
    print(f"DEBUG: Delete Request for file_id={file_id}")
    db = SessionLocal()
    
    try:
        # 1. Check Audio File Existence
        audio = db.query(models.ToeicAudioFile).filter(models.ToeicAudioFile.id == file_id).first()
        print(f"DEBUG: Query result for id={file_id}: {audio}")
        
        if not audio:
            print(f"ERROR: Audio file with id={file_id} NOT FOUND.")
            db.close()
            raise HTTPException(status_code=404, detail=f"Audio file {file_id} not found.")

        saved_path = audio.saved_path
        
        # 2. Raw SQL Deletion
        print(f"DEBUG: Deleting Transcripts for Audio {file_id}")
        db.execute(text("DELETE FROM toeic_transcripts WHERE question_id IN (SELECT id FROM toeic_questions WHERE audio_id = :aid)"), {"aid": file_id})
        
        print(f"DEBUG: Deleting Questions for Audio {file_id}")
        db.execute(text("DELETE FROM toeic_questions WHERE audio_id = :aid"), {"aid": file_id})
        
        print(f"DEBUG: Deleting Audio Record {file_id}")
        db.execute(text("DELETE FROM toeic_audio_files WHERE id = :aid"), {"aid": file_id})
        
        db.commit()
        print("DEBUG: DB Deletion Committed.")

        # 3. Delete Physical File
        if saved_path and os.path.exists(saved_path):
            try:
                os.remove(saved_path)
                print(f"Deleted physical file: {saved_path}")
            except Exception as e:
                print(f"Warning: Failed to delete physical file {saved_path}: {e}")

        return {"message": "File and all related data deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Critical Error during file deletion: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
    finally:
        db.close()

@app.get("/lc/debug/files")
def debug_files(db: Session = Depends(get_db)):
    audios = db.query(models.ToeicAudioFile).all()
    return [{"id": a.id, "filename": a.filename, "status": a.status} for a in audios]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_server:app", host="0.0.0.0", port=8000, reload=True)
