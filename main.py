import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("formwork")

import re

from formwork.ai_solver import solve_questions
from formwork.form_filler import fill_form
from formwork.form_parser import parse_form
from formwork.google_auth import login_google

NAME_PATTERN = re.compile(
    r"(名前|氏名|姓名|なまえ|your\s*name|name)", re.IGNORECASE
)
NUMBER_PATTERN = re.compile(
    r"(出席番号|出席番號|学籍番号|學號|番号|番號|student\s*(number|id))",
    re.IGNORECASE,
)


async def run(
    form_url: str,
    email: str,
    password: str,
    gemini_key: str,
    *,
    pro: bool = False,
    student_name: str = "",
    student_number: str = "",
):
    p, browser, context = await login_google(email, password)

    try:
        page = await context.new_page()
        page_num = 1
        total_questions = 0
        all_unfilled: list[tuple[int, str]] = []

        while True:
            questions = await parse_form(page, form_url if page_num == 1 else None)

            if not questions:
                logger.warning("沒有解析到任何題目，請檢查表單 URL")
                break

            for q in questions:
                text = q.text.replace("\n", " ").strip()
                if student_number and NUMBER_PATTERN.search(text):
                    # 先比對學號關鍵字，避免「出席番号」被誤判成姓名相關題目
                    q.auto_answer = student_number
                    logger.info("自動填入學號：%s = %s", text, student_number)
                elif student_name and NAME_PATTERN.search(text):
                    q.auto_answer = student_name
                    logger.info("自動填入姓名：%s = %s", text, student_name)

            answers = solve_questions(questions, gemini_key, pro=pro)
            page_unfilled = await fill_form(page, questions, answers)
            all_unfilled.extend(
                (total_questions + idx, text) for idx, text in page_unfilled
            )
            total_questions += len(questions)

            next_btn = await page.query_selector('div[role="button"] span')
            found_next = False
            if next_btn:
                all_btns = await page.query_selector_all('div[role="button"] span')
                for btn in all_btns:
                    text = (await btn.inner_text()).strip()
                    if text in ("次へ", "Next", "下一頁", "下一步", "繼續"):
                        parent = await btn.evaluate_handle(
                            "el => el.closest('[role=\"button\"]')"
                        )
                        await parent.click()
                        page_num += 1
                        logger.info("前往第 %d 頁", page_num)
                        await page.wait_for_timeout(2000)
                        found_next = True
                        break

            if not found_next:
                break

        filled_count = total_questions - len(all_unfilled)
        logger.info("作答完成度：%d/%d", filled_count, total_questions)
        if all_unfilled:
            logger.warning("以下題目未成功填寫：")
            for num, text in all_unfilled:
                logger.warning("  題號 %d: %s", num, text)

        input("填寫完成，按 Enter 關閉瀏覽器...")
    finally:
        await context.storage_state(
            path=str(Path(__file__).parent / "auth_state" / "google_state.json")
        )
        await browser.close()
        await p.stop()


def main():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger("formwork").setLevel(logging.INFO)
    logging.getLogger("formwork").addHandler(handler)
    load_dotenv()

    parser = argparse.ArgumentParser(description="Google 表單自動填寫工具")
    parser.add_argument("--url", help="Google 表單 URL")
    parser.add_argument("-p", "--pro", help="使用專業版功能", action="store_true")
    args = parser.parse_args()
    if not args.url:
        args.url = input("請輸入 Google 表單 URL：")

    email = os.getenv("GOOGLE_EMAIL")
    password = os.getenv("GOOGLE_PASSWORD")
    gemini_key = os.getenv("GEMINI_API_KEY")
    student_name = os.getenv("STUDENT_NAME", "")
    student_number = os.getenv("STUDENT_NUMBER", "")

    if not email or not password:
        logger.error("請在 .env 中設定 GOOGLE_EMAIL 和 GOOGLE_PASSWORD")
        sys.exit(1)
    if not gemini_key:
        logger.error("請在 .env 中設定 GEMINI_API_KEY")
        sys.exit(1)

    try:
        asyncio.run(
            run(
                args.url,
                email,
                password,
                gemini_key,
                pro=args.pro,
                student_name=student_name,
                student_number=student_number,
            )
        )
    except KeyboardInterrupt:
        logger.warning("已中斷，結束程式")
        sys.exit(130)


if __name__ == "__main__":
    main()
