from faster_whisper import WhisperModel
import os

# 모델 로드는 비용이 크므로 전역으로 관리하거나 필요시 로드 (여기서는 함수 호출 시 로드하지만, 프로덕션에서는 전역 로드 권장)
# 메모리 절약을 위해 base 모델 사용
MODEL_SIZE = "base"

def transcribe_audio_file(file_path: str):
    """
    Audio file path를 받아서 세그먼트 리스트를 반환합니다.
    """
    # CPU 또는 GPU 설정 (CUDA 가용 여부에 따라 자동 설정하려면 로직 추가 필요)
    # 안전하게 cpu + int8 로 시작
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    segments, info = model.transcribe(file_path, beam_size=5)
    
    result = []
    for segment in segments:
        result.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        })
        
    return result
