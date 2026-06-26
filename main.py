import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from google_auth import login_google
from form_parser import parse_form
from ai_solver import solve_questions
from form_filler import fill_form


async def run(form_url: str, email: str, password: str, gemini_key: str):
    p, browser, context = await login_google(email, password)

    try:
        page = await context.new_page()
        questions = await parse_form(page, form_url)

        if not questions:
            print("沒有解析到任何題目，請檢查表單 URL")
            return

        answers = solve_questions(questions, gemini_key)
        await fill_form(page, questions, answers)
        input("填寫完成，按 Enter 關閉瀏覽器...")
    finally:
        await context.storage_state(path=str(Path(__file__).parent / "auth_state" / "google_state.json"))
        await browser.close()
        await p.stop()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Google 表單自動填寫工具")
    parser.add_argument("--url", required=True, help="Google 表單 URL")
    args = parser.parse_args()

    email = os.getenv("GOOGLE_EMAIL")
    password = os.getenv("GOOGLE_PASSWORD")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not email or not password:
        print("請在 .env 中設定 GOOGLE_EMAIL 和 GOOGLE_PASSWORD")
        sys.exit(1)
    if not gemini_key:
        print("請在 .env 中設定 GEMINI_API_KEY")
        sys.exit(1)

    asyncio.run(run(args.url, email, password, gemini_key))


if __name__ == "__main__":
    main()
