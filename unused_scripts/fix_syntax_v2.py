
import re
path = r"c:\toeic_whisper\frontend\app\page.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the specific error using regex to catch whitespace
fixed_content = re.sub(r"</main\s*>", "</main>", content)

with open(path, "w", encoding="utf-8") as f:
    f.write(fixed_content)

print("Fixed </main> error with regex.")
