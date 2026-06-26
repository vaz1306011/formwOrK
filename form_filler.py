from __future__ import annotations

from playwright.async_api import Page
from form_parser import Question


async def fill_form(page: Page, questions: list[Question], answers: list[str]):
    question_blocks = await page.query_selector_all('[role="listitem"]')

    q_idx = 0
    for block in question_blocks:
        heading = await block.query_selector('[role="heading"]')
        if not heading:
            continue
        if q_idx >= len(questions):
            break

        q = questions[q_idx]
        answer = answers[q_idx]
        q_idx += 1

        if q.question_type == "radio":
            await _fill_radio(block, answer)
        elif q.question_type == "checkbox":
            await _fill_checkbox(block, answer)
        elif q.question_type == "dropdown":
            await _fill_dropdown(block, answer)
        elif q.question_type in ("short_answer", "paragraph"):
            await _fill_text(block, q.question_type, answer)

    print("所有題目已填寫完成，未送出（依設定跳過送出）")


def _normalize(text: str) -> str:
    import re
    return re.sub(r'^[A-Za-z0-9]\s*[\.\)．）:：]\s*', '', text).strip().lower()


async def _fill_radio(block, answer: str):
    radios = await block.query_selector_all('[role="radio"]')
    norm_answer = _normalize(answer)
    for r in radios:
        label = await r.get_attribute("aria-label")
        if not label:
            continue
        norm_label = _normalize(label)
        if norm_label == norm_answer or norm_label in norm_answer or norm_answer in norm_label:
            await r.click()
            return


async def _fill_checkbox(block, answer: str):
    selected = [_normalize(a) for a in answer.split(",")]
    checkboxes = await block.query_selector_all('[role="checkbox"]')
    for cb in checkboxes:
        label = await cb.get_attribute("aria-label")
        if not label:
            continue
        norm_label = _normalize(label)
        if any(norm_label == s or norm_label in s or s in norm_label for s in selected):
            await cb.click()


async def _fill_dropdown(block, answer: str):
    listbox = await block.query_selector('[role="listbox"]')
    if listbox:
        await listbox.click()
        await block.page.wait_for_timeout(500)
        options = await block.page.query_selector_all('[role="option"]')
        for opt in options:
            text = (await opt.inner_text()).strip()
            if answer.strip().lower() in text.lower():
                await opt.click()
                return


async def _fill_text(block, q_type: str, answer: str):
    if q_type == "paragraph":
        inp = await block.query_selector("textarea")
    else:
        inp = await block.query_selector('input[type="text"]')
    if inp:
        await inp.fill(answer)
