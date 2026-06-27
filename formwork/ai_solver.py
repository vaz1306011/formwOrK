from __future__ import annotations

import logging
import time

from google import genai
from google.genai.errors import APIError

from .form_parser import Question

logger = logging.getLogger(__name__)

MODELS_DEFAULT = ["gemini-2.5-flash", "gemini-2.0-flash"]
MODELS_PRO = ["gemini-3.1-pro-preview", "gemini-2.5-flash"]


def solve_questions(
    questions: list[Question], gemini_key: str, *, pro: bool = False
) -> list[str]:
    client = genai.Client(api_key=gemini_key)
    models = MODELS_PRO if pro else MODELS_DEFAULT
    logger.info("使用模型: %s", models[0])
    answers: list[str] = []

    for q in questions:
        answer = _solve(client, q, models)
        answers.append(answer)
        logger.info(f"題目 {q.index + 1}: {q.text[:40]}... → {answer[:60]}")

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
            except Exception as e:
                logger.error("%s 失敗: %s", model, e)
                break
    return "（無法作答）"


def _build_prompt(q: Question) -> str:
    if q.question_type in ("radio", "checkbox", "dropdown"):
        options_str = "\n".join(f"  {opt}" for opt in q.options)
        kind = "複数選択" if q.question_type == "checkbox" else "単一選択"
        return (
            f"これは{kind}問題です。\n"
            f"選択肢の内容は本文または画像に含まれることがありますが、解答は必ず下の「選択可能なラベル」一覧の中から選び、"
            f"そのラベルだけをそのまま出力してください（例:「ウ」や「C」）。選択肢の内容文や説明は一切出力しないでください。\n"
            f"複数選択の場合はラベルをカンマで区切ってください。\n\n"
            f"問題：{q.text}\n"
            f"選択可能なラベル（この中から選ぶこと）：\n{options_str}\n\n"
            f"解答ラベル："
        )
    else:
        return (
            f"これは記述問題です。簡潔に解答だけを出力し、余計な説明は加えないでください。\n\n"
            f"問題：{q.text}\n\n"
            f"解答："
        )
