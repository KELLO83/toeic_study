from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import shutil
import os
import aiofiles
from database import engine, get_db, Base
from models import AudioFile, Transcript
import transcriber

# DB 초기화 (테이블 생성)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def process_audio_background(audio_id: int, file_path: str, db: Session):
    """
    백그라운드에서 실행될 변환 작업
    """
    try:
        # DB 세션을 새로 열어야 할 수도 있음 (여기서는 전달받은 세션 사용 주의 -> 스레드 안전성)
        # BackgroundTasks에서 실행되므로 별도 세션 생성 권장
        from database import SessionLocal
        db_bg = SessionLocal()
        
        audio_record = db_bg.query(AudioFile).filter(AudioFile.id == audio_id).first()
        if not audio_record:
            db_bg.close()
            return

        audio_record.status = "processing"
        db_bg.commit()

        # Whisper 변환
        segments = transcriber.transcribe_audio_file(file_path)

        # 결과 저장
        for seg in segments:
            transcript = Transcript(
                audio_id=audio_id,
                start_time=seg['start'],
                end_time=seg['end'],
                text=seg['text']
            )
            db_bg.add(transcript)
        
        audio_record.status = "completed"
        db_bg.commit()
        db_bg.close()
        
    except Exception as e:
        print(f"Error processing audio: {e}")
        # 에러 처리 로직
        from database import SessionLocal
        db_bg = SessionLocal()
        audio_record = db_bg.query(AudioFile).filter(AudioFile.id == audio_id).first()
        if audio_record:
            audio_record.status = "error"
            db_bg.commit()
        db_bg.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/api/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    
    # 비동기로 파일 저장
    async with aiofiles.open(file_location, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    # DB 레코드 생성
    new_audio = AudioFile(filename=file.filename, saved_path=file_location, status="pending")
    db.add(new_audio)
    db.commit()
    db.refresh(new_audio)
    
    # 백그라운드 작업 시작
    background_tasks.add_task(process_audio_background, new_audio.id, file_location, db)
    
    return {"id": new_audio.id, "filename": new_audio.filename, "status": "pending"}

@app.get("/api/history")
def get_history(db: Session = Depends(get_db)):
    files = db.query(AudioFile).order_by(AudioFile.upload_date.desc()).all()
    return files

@app.get("/player/{audio_id}", response_class=HTMLResponse)
async def player_page(request: Request, audio_id: int, db: Session = Depends(get_db)):
    audio = db.query(AudioFile).filter(AudioFile.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="File not found")
    return templates.TemplateResponse("player.html", {"request": request, "audio": audio})

@app.get("/api/transcripts/{audio_id}")
def get_transcripts(audio_id: int, db: Session = Depends(get_db)):
    audio = db.query(AudioFile).filter(AudioFile.id == audio_id).first()
    if not audio:
        raise HTTPException(status_code=404, detail="File not found")
        
    if audio.status != "completed":
        return {"status": audio.status, "data": []}
        
    transcripts = db.query(Transcript).filter(Transcript.audio_id == audio_id).order_by(Transcript.start_time).all()
    return {"status": "completed", "data": transcripts}

