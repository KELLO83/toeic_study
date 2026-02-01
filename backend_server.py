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
from faster_whisper import WhisperModel
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

# Whisper Model Initialization (Base model for speed/accuracy balance)
print("Loading Whisper Model...")
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
print("Whisper Model Loaded.")

@app.get("/")
def read_root():
    return {"message": "TOEIC Whisper Backend is running!"}

from fastapi import Depends

@app.get("/words")
def get_words(limit: int = 100, db: Session = Depends(get_db)):
    try:
        words = db.query(models.ToeicWord).limit(limit).all()
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

        # 1. Run Whisper
        print("DEBUG: Calling whisper_model.transcribe...")
        segments, info = whisper_model.transcribe(file_path, beam_size=5)
        total_duration = info.duration
        print(f"DEBUG: Transcription started. Total Duration: {total_duration}s")
        
        current_question = None
        current_part = 0  # Default Part
        last_progress_update = 0 
        
        # Buffer for dialogue/instruction text that appears BEFORE the question "Number X"
        pending_context = [] 
        # Tracks if we are "inside" a question set block (e.g., questions 4-6)
        # Format: {"start": 4, "end": 6, "context_transcripts": []}
        active_set_info = None

        processed_segments = 0
        for segment in segments:
            processed_segments += 1
            text = segment.text.strip()
            start = segment.start
            end = segment.end
            
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

            
            # 3-2. Detect Individual Question Start (e.g., "Number 1", "Question 1")
            q_match = re.search(r"(Number|Question)\s*(\d+)", text, re.IGNORECASE)
            
            if set_match:
                # Start of a new set.
                current_question = None 
                
                start_q = int(set_match.group(2))  # Changed from group(1)
                end_q = int(set_match.group(4))    # Changed from group(3)

                
                # Initialize new set info
                active_set_info = {
                    "start": start_q,
                    "end": end_q,
                    "context_transcripts": []
                }
                
                # The instruction itself is part of the context
                transcript_obj = {"start": start, "end": end, "text": text}
                pending_context.append(transcript_obj)
                
                # Also save to active set context for later questions
                active_set_info["context_transcripts"].append(transcript_obj)
                
            elif q_match:
                q_val = int(q_match.group(2))
                
                # Determine set number
                current_set_num = None
                if active_set_info and active_set_info["start"] <= q_val <= active_set_info["end"]:
                    current_set_num = active_set_info["start"]
                else:
                    active_set_info = None

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
                            label="conversation" # Context is conversation
                        )
                        db.add(db_transcript)
                        if ctx["start"] < current_question.start_time:
                            current_question.start_time = ctx["start"]
                    pending_context = []
                
                # Attach Context (Conversation) - Inherited from Set
                elif active_set_info and active_set_info["context_transcripts"]:
                    for ctx in active_set_info["context_transcripts"]:
                         db_transcript = models.ToeicTranscript(
                            question_id=current_question.id,
                            start_time=ctx["start"],
                            end_time=ctx["end"],
                            text=ctx["text"],
                            label="conversation" # Context is conversation
                        )
                         db.add(db_transcript)
                         if ctx["start"] < current_question.start_time:
                            current_question.start_time = ctx["start"]
                
                # Finally, add the Question Text itself ("Number X...")
                # This segment is definitely a question reading.
                db_transcript = models.ToeicTranscript(
                    question_id=current_question.id,
                    start_time=start,
                    end_time=end,
                    text=text,
                    label="question" # Marking as question text
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
                    # EXCEPT if it's the conversation continuing? No, conversation happens BEFORE questions in Part 3/4.
                    # So anything added to `current_question` via `else` is Question Reading.
                    db_transcript.label = "question" 
                    db.add(db_transcript)
                else:
                    # Context appearing before a question
                    pending_context.append(transcript_obj)
                    if active_set_info:
                        active_set_info["context_transcripts"].append(transcript_obj)

            # 4. Add to Transcripts -> Moved inside logical blocks above
            
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
