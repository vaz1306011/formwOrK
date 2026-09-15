from __future__ import annotations

import logging
import time

from google import genai
from google.genai.errors import APIError

from .form_parser import Question

logger = logging.getLogger(__name__)

MODELS_DEFAULT = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]
MODELS_PRO = ["gemini-3.1-pro-preview", "gemini-3.8-flash"]


def solve_questions(
    questions: list[Question], gemini_key: str, *, pro: bool = False
) -> list[str]:
    client = genai.Client(api_key=gemini_key)
    models = MODELS_PRO if pro else MODELS_DEFAULT
    logger.info("使用模型: %s", models[0])
    answers: list[str] = []

    try:
        for q in questions:
            if q.auto_answer:
                answers.append(q.auto_answer)
                logger.info(
                    "題目 %d: %s... → %s (自動填入)",
                    q.index + 1,
                    q.text[:40],
                    q.auto_answer,
                )
                continue
            answer = _solve(client, q, models)
            answers.append(answer)
            logger.info("題目 %d: %s... → %s", q.index + 1, q.text[:40], answer[:60])
    except KeyboardInterrupt:
        logger.warning("使用者中斷，停止作答")
        raise

    return answers


def _solve(client: genai.Client, q: Question, models: list[str]) -> str:
    parts: list[dict] = [{"text": _build_prompt(q)}]
    if q.image_base64:
        parts.append(
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": q.image_base64,
                }
            }
        )
    contents = [{"parts": parts}]

    for model in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model, contents=contents
                )
                return response.text.strip()
            except APIError as e:
                if e.code == 429:
                    wait = 35 * (attempt + 1)
                    logger.warning("%s 速率限制，等待 %d 秒後重試...", model, wait)
                    time.sleep(wait)
                else:
                    logger.error("%s 失敗: %s", model, e)
                    break
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error("%s 失敗: %s", model, e)
                break
    return "（無法作答）"


def _build_prompt(q: Question) -> str:
    context_str = f"背景情報：{q.context}\n\n" if q.context else ""

    if q.question_type in ("radio", "checkbox", "dropdown"):
        options_str = "\n".join(f"  {opt}" for opt in q.options)
        kind = "複数選択" if q.question_type == "checkbox" else "単一選択"
        return (
            f"{context_str}"
            f"これは{kind}問題です。\n"
            f"解答は必ず下の「選択可能なラベル」一覧の中から一つそのまま選び出力してください。\n"
            f"一覧内の項目が「ア」「A」のような記号で始まる場合はその記号だけを出力してください。"
            f"記号が付いていない場合は、その項目のテキストを一言一句そのまま出力してください（絶対に自分で記号を作らないこと）。\n"
            f"説明・理由・言い換えは一切出力せず、選んだラベルまたはテキストのみを出力してください。\n"
            f"複数選択の場合はラベルをカンマで区切ってください。\n\n"
            f"問題：{q.text}\n"
            f"選択可能なラベル（この中から選ぶこと）：\n{options_str}\n\n"
            f"解答ラベル："
        )
    else:
        return (
            f"{context_str}"
            f"これは記述問題です。簡潔に解答だけを出力し、余計な説明は加えないでください。\n\n"
            f"問題：{q.text}\n\n"
            f"解答："
        )
