# -
News summary
"""
한경 글로벌마켓 유튜브 채널 최신 영상 자동 요약 스크립트
"""

import os
import json
import smtplib
import datetime
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yt_dlp
import anthropic
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

# ── 설정 ──────────────────────────────────────────────
CHANNEL_URL = "https://www.youtube.com/@한경글로벌마켓/videos"
CHANNEL_ID  = "UCWskYkV4c4S9D__rsfOl2JA"
MAX_VIDEOS  = 1   # 최신 영상 몇 개까지 처리할지

# ── 1. 최신 영상 정보 가져오기 ────────────────────────
def get_latest_videos(max_count: int = 1) -> list[dict]:
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlist_items": f"1:{max_count}",
    }
    url = f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    
    videos = []
    for entry in info.get("entries", []):
        videos.append({
            "id":    entry["id"],
            "title": entry.get("title", "제목 없음"),
            "url":   f"https://www.youtube.com/watch?v={entry['id']}",
        })
    return videos


# ── 2. 자막 추출 ──────────────────────────────────────
def get_transcript(video_id: str) -> str:
    try:
        # 한국어 자막 우선, 없으면 자동 생성 자막
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["ko", "ko-KR"]
        )
    except NoTranscriptFound:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["en"]
            )
        except Exception:
            return ""
    except TranscriptsDisabled:
        return ""
    except Exception:
        return ""

    return " ".join([t["text"] for t in transcript_list])


# ── 3. Claude API로 요약 ──────────────────────────────
def summarize(title: str, transcript: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    if not transcript:
        return "⚠️ 자막을 가져올 수 없어 요약을 생성하지 못했습니다."

    # 자막이 너무 길면 앞 12,000자만 사용 (토큰 절약)
    trimmed = transcript[:12000]

    prompt = f"""
아래는 한경 글로벌마켓 유튜브 방송 「{title}」의 자막입니다.
투자자 관점에서 핵심 내용을 한국어로 요약해 주세요.

형식:
1. 📌 핵심 요약 (3줄 이내)
2. 📈 주요 시장 이슈 (bullet point)
3. 💡 언급된 종목 / 섹터
4. 🔮 전망 및 주목 포인트

자막:
{trimmed}
"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── 4. 이메일 전송 ────────────────────────────────────
def send_email(subject: str, body: str) -> None:
    sender   = os.environ.get("EMAIL_ADDRESS", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    receiver = os.environ.get("TO_EMAIL", sender)

    if not sender or not password:
        print("이메일 설정이 없습니다. 파일로만 저장합니다.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"✅ 이메일 전송 완료 → {receiver}")
    except Exception as e:
        print(f"❌ 이메일 전송 실패: {e}")


# ── 5. 파일 저장 ──────────────────────────────────────
def save_to_file(content: str) -> str:
    today    = datetime.date.today().strftime("%Y%m%d")
    filename = f"summary_{today}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 파일 저장: {filename}")
    return filename


# ── 메인 ──────────────────────────────────────────────
def main():
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    print(f"[{today}] 한경 글로벌마켓 요약 시작")

    videos = get_latest_videos(MAX_VIDEOS)
    if not videos:
        print("❌ 영상을 찾을 수 없습니다.")
        return

    all_summaries = []

    for video in videos:
        print(f"\n▶ 처리 중: {video['title']}")
        transcript = get_transcript(video["id"])
        summary    = summarize(video["title"], transcript)

        block = f"""{'='*60}
📺 {video['title']}
🔗 {video['url']}
{'='*60}

{summary}
"""
        all_summaries.append(block)
        print(block)

    full_text = f"한경 글로벌마켓 일일 요약 | {today}\n\n" + "\n".join(all_summaries)

    # 파일 저장
    save_to_file(full_text)

    # 이메일 전송 (설정된 경우)
    send_email(f"[한경글로벌마켓] {today} 요약", full_text)


if __name__ == "__main__":
    main()
