from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
import requests
import json
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine, get_db
import models

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

@app.get("/")
def read_root():
    return {"message": "TOEIC Whisper Backend is running!"}
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
import edge_tts
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_server:app", host="0.0.0.0", port=8000, reload=True)
