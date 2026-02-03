import os
import io
import zipfile
import shutil
import requests
import sys

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

def install_ffmpeg():
    print(f"Downloading FFmpeg from {FFMPEG_URL}...")
    print("This may take a minute based on your internet speed (approx 80MB)...")
    
    try:
        response = requests.get(FFMPEG_URL, stream=True)
        response.raise_for_status()
        
        print("Download complete. Extracting...")
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Check structure (usually ffmpeg-ver-essentials/bin/ffmpeg.exe)
            for file_info in z.infolist():
                if file_info.filename.endswith("bin/ffmpeg.exe"):
                    print("Found ffmpeg.exe, extracting...")
                    with z.open(file_info) as source, open("ffmpeg.exe", "wb") as target:
                        shutil.copyfileobj(source, target)
                        
                elif file_info.filename.endswith("bin/ffprobe.exe"):
                    print("Found ffprobe.exe, extracting...")
                    with z.open(file_info) as source, open("ffprobe.exe", "wb") as target:
                        shutil.copyfileobj(source, target)

        print("Checking files...")
        if os.path.exists("ffmpeg.exe") and os.path.exists("ffprobe.exe"):
            print("✅ FFmpeg & FFprobe installed successfully in current directory!")
            print("You can now run 'python backend_server.py' without issues.")
        else:
            print("❌ Failed to extract files. Please check the zip structure or try manual installation.")

    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print("Fallback: Please download manually from https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")
        print("And copy ffmpeg.exe, ffprobe.exe to this folder.")

if __name__ == "__main__":
    install_ffmpeg()
