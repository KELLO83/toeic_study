"""DB 조회 스크립트 - 문제 확인용"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port='5432', 
    database='toeic',
    user='postgres',
    password='1234'
)
cur = conn.cursor()

# 최신 audio_id 가져오기
cur.execute('SELECT MAX(id) FROM lc_audio')
latest_audio_id = cur.fetchone()[0]
print(f"Latest audio_id: {latest_audio_id}")

# Number 42 포함된 레코드 찾기
cur.execute("""
    SELECT id, question_number, start_time, end_time, transcript 
    FROM lc_questions 
    WHERE audio_id = %s AND transcript LIKE '%%Number 42%%'
    ORDER BY start_time
""", (latest_audio_id,))

rows = cur.fetchall()
print(f"\n=== 'Number 42' 포함 레코드: {len(rows)}개 ===")
for r in rows:
    print(f"ID:{r[0]} Q:{r[1]} Start:{r[2]:.2f} End:{r[3]:.2f}")
    print(f"  Text: {r[4][:150]}...")
    print()

# Q42 주변 레코드 확인 (question_number 41, 42, 43)
cur.execute("""
    SELECT id, question_number, start_time, end_time, transcript 
    FROM lc_questions 
    WHERE audio_id = %s AND question_number IN (41, 42, 43)
    ORDER BY question_number
""", (latest_audio_id,))

rows = cur.fetchall()
print(f"\n=== Question 41, 42, 43 주변 레코드 ===")
for r in rows:
    print(f"ID:{r[0]} Q:{r[1]} Start:{r[2]:.2f} End:{r[3]:.2f}")
    print(f"  Text: {r[4][:150]}...")
    print()

# A/B/C 선택지 확인 (transcript가 A. 또는 B. 또는 C.로 시작하는 것)
cur.execute("""
    SELECT id, question_number, start_time, end_time, transcript 
    FROM lc_questions 
    WHERE audio_id = %s AND (transcript LIKE 'A.%%' OR transcript LIKE 'B.%%' OR transcript LIKE 'C.%%')
    ORDER BY start_time
    LIMIT 10
""", (latest_audio_id,))

rows = cur.fetchall()
print(f"\n=== A/B/C 선택지 샘플 (처음 10개) ===")
for r in rows:
    print(f"ID:{r[0]} Q:{r[1]} Start:{r[2]:.2f} End:{r[3]:.2f}")
    print(f"  Text: {r[4][:100]}")
    print()

conn.close()
