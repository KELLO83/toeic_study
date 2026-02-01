
import re
import os

path = r"c:\toeic_whisper\frontend\app\page.tsx"
if not os.path.exists(path):
    print(f"File not found: {path}")
    exit(1)

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Content length before: {len(content)}")
match = re.search(r"</main\s*>", content)
if match:
    print(f"Found match: '{match.group(0)}' at {match.start()}")
else:
    print("No match found for </main >")
    # print tail to see what it is
    print("Tail of file:")
    print(content[-50:])

# Fix
fixed_content = re.sub(r"</main\s*>", "</main>", content)

if content == fixed_content:
    print("No changes made.")
else:
    with open(path, "w", encoding="utf-8") as f:
        f.write(fixed_content)
    print("File updated.")
