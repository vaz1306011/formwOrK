from __future__ import annotations

import logging
from collections import defaultdict

from playwright.async_api import Page

from .form_parser import Question

logger = logging.getLogger(__name__)


async def fill_form(
    page: Page, questions: list[Question], answers: list[str]
) -> list[tuple[int, str]]:
    question_blocks = await page.query_selector_all('[role="listitem"]')
    q_map: dict[int, list[tuple[Question, str]]] = defaultdict(list)
    for q, a in zip(questions, answers):
        q_map[q.index].append((q, a))

    unfilled: list[tuple[int, str]] = []

    for i, block in enumerate(question_blocks):
        if i not in q_map:
            continue

        for q, answer in q_map[i]:
            logger.info("開始填寫題目 %d: %s", q.index + 1, answer[:60])

            filled = False
            if q.question_type == "radio":
                if q.grid_row is not None:
                    filled = await _fill_grid_radio(block, q.grid_row, answer)
                else:
                    filled = await _fill_radio(block, answer)
            elif q.question_type == "checkbox":
                if q.grid_row is not None:
                    filled = await _fill_grid_checkbox(block, q.grid_row, answer)
                else:
                    filled = await _fill_checkbox(block, answer)
            elif q.question_type == "dropdown":
                filled = await _fill_dropdown(block, answer)
            elif q.question_type in ("short_answer", "paragraph"):
                filled = await _fill_text(block, q.question_type, answer)

            if not filled:
                logger.warning("題目 %d 無法填入答案: %s", q.index + 1, answer[:60])
                unfilled.append((q.index + 1, q.text.strip()))

    return unfilled


def _normalize(text: str) -> str:
    import re

    return re.sub(r"^[A-Za-z0-9]\s*[\.\)．）:：]\s*", "", text).strip().lower()


def _split_prefix(text: str) -> tuple[str | None, str]:
    """把「A. 第一セクター」拆成 ("a", "第一セクター")，沒有記號前綴則回傳 (None, 原文)"""
    import re

    m = re.match(r"^([A-Za-z0-9])\s*[\.\)．）:：]\s*(.*)$", text.strip())
    if m:
        return m.group(1).lower(), m.group(2).strip().lower()
    return None, text.strip().lower()


def _matches(label: str, answer: str) -> bool:
    norm_answer = _normalize(answer)
    raw_answer = answer.strip().lower()
    prefix, rest = _split_prefix(label)
    answer_prefix, _ = _split_prefix(answer)
    full_norm_label = _normalize(label)

    # AI 只回答記號本身（例如「A」或「A.」），對應選項前綴
    if prefix and (
        raw_answer == prefix
        or norm_answer == prefix
        or (answer_prefix is not None and answer_prefix == prefix)
    ):
        return True

    if full_norm_label == norm_answer or full_norm_label == raw_answer:
        return True

    # 避免單一字元的子字串誤判，只在答案有一定長度時做包含比對
    if len(norm_answer) > 1 and (
        full_norm_label in norm_answer or norm_answer in full_norm_label
    ):
        return True
    if rest and len(norm_answer) > 1 and (rest in norm_answer or norm_answer in rest):
        return True

    return False


async def _fill_radio(block, answer: str) -> bool:
    radios = await block.query_selector_all('[role="radio"]')
    for r in radios:
        label = await r.get_attribute("aria-label")
        if not label:
            continue
        if _matches(label, answer):
            if await r.get_attribute("aria-checked") == "true":
                return True
            await r.click()
            return True
    return False


async def _fill_grid_radio(block, row_index: int, answer: str) -> bool:
    radiogroups = await block.query_selector_all('[role="radiogroup"]')
    if row_index >= len(radiogroups):
        return False
    return await _fill_radio(radiogroups[row_index], answer)


async def _fill_grid_checkbox(block, row_index: int, answer: str) -> bool:
    groups = await block.query_selector_all('[role="group"]')
    if row_index >= len(groups):
        return False
    return await _fill_checkbox(groups[row_index], answer)


async def _fill_checkbox(block, answer: str) -> bool:
    selected = [a.strip() for a in answer.split(",") if a.strip()]
    checkboxes = await block.query_selector_all('[role="checkbox"]')
    filled = False
    for cb in checkboxes:
        label = await cb.get_attribute("aria-label")
        if not label:
            continue
        if any(_matches(label, s) for s in selected):
            if await cb.get_attribute("aria-checked") != "true":
                await cb.click()
            filled = True
    return filled


async def _fill_dropdown(block, answer: str) -> bool:
    listbox = await block.query_selector('[role="listbox"]')
    if listbox:
        await listbox.click()
        await block.page.wait_for_timeout(500)
        options = await block.page.query_selector_all('[role="option"]')
        for opt in options:
            text = (await opt.inner_text()).strip()
            if _matches(text, answer):
                await opt.click()
                return True
    return False


async def _fill_text(block, q_type: str, answer: str) -> bool:
    if q_type == "paragraph":
        inp = await block.query_selector("textarea")
    else:
        inp = await block.query_selector('input[type="text"]')
    if inp:
        await inp.fill(answer)
        return True
    return False
