
path = r"c:\toeic_whisper\frontend\app\page.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the specific error
fixed_content = content.replace("</main >", "</main>")

with open(path, "w", encoding="utf-8") as f:
    f.write(fixed_content)

print("Fixed </main > error.")
