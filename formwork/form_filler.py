from __future__ import annotations

import logging

from playwright.async_api import Page

from .form_parser import Question

logger = logging.getLogger(__name__)


async def fill_form(page: Page, questions: list[Question], answers: list[str]):
    question_blocks = await page.query_selector_all('[role="listitem"]')
    q_map = {q.index: (q, a) for q, a in zip(questions, answers)}

    for i, block in enumerate(question_blocks):
        if i not in q_map:
            continue

        q, answer = q_map[i]

        logger.info("開始填寫題目 %d: %s", q.index + 1, answer[:60])

        filled = False
        if q.question_type == "radio":
            filled = await _fill_radio(block, answer)
        elif q.question_type == "checkbox":
            filled = await _fill_checkbox(block, answer)
        elif q.question_type == "dropdown":
            filled = await _fill_dropdown(block, answer)
        elif q.question_type in ("short_answer", "paragraph"):
            filled = await _fill_text(block, q.question_type, answer)

        if not filled:
            logger.warning("題目 %d 無法填入答案: %s", q.index + 1, answer[:60])

    logger.info("所有題目已填寫完成")


def _normalize(text: str) -> str:
    import re

    return re.sub(r"^[A-Za-z0-9]\s*[\.\)．）:：]\s*", "", text).strip().lower()


async def _fill_radio(block, answer: str) -> bool:
    radios = await block.query_selector_all('[role="radio"]')
    norm_answer = _normalize(answer)
    for r in radios:
        label = await r.get_attribute("aria-label")
        if not label:
            continue
        norm_label = _normalize(label)
        if (
            norm_label == norm_answer
            or norm_label in norm_answer
            or norm_answer in norm_label
        ):
            if await r.get_attribute("aria-checked") == "true":
                return True
            await r.click()
            return True
    return False


async def _fill_checkbox(block, answer: str) -> bool:
    selected = [_normalize(a) for a in answer.split(",")]
    checkboxes = await block.query_selector_all('[role="checkbox"]')
    filled = False
    for cb in checkboxes:
        label = await cb.get_attribute("aria-label")
        if not label:
            continue
        norm_label = _normalize(label)
        if any(norm_label == s or norm_label in s or s in norm_label for s in selected):
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
            if answer.strip().lower() in text.lower():
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
