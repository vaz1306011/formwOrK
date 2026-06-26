from __future__ import annotations

import base64
from dataclasses import dataclass, field
from playwright.async_api import Page


@dataclass
class Question:
    index: int
    text: str
    question_type: str  # "radio" | "checkbox" | "dropdown" | "short_answer" | "paragraph"
    options: list[str] = field(default_factory=list)
    image_base64: str | None = None


async def parse_form(page: Page, url: str) -> list[Question]:
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_selector('[role="listitem"]', timeout=15000)

    question_blocks = await page.query_selector_all('[role="listitem"]')
    questions: list[Question] = []

    for i, block in enumerate(question_blocks):
        heading = await block.query_selector('[role="heading"]')
        if not heading:
            continue

        text = (await heading.inner_text()).strip()

        img = await block.query_selector("img")
        image_base64 = None
        if img:
            screenshot_bytes = await img.screenshot()
            image_base64 = base64.b64encode(screenshot_bytes).decode()

        radios = await block.query_selector_all('[role="radio"]')
        checkboxes = await block.query_selector_all('[role="checkbox"]')
        dropdown = await block.query_selector('[role="listbox"]')
        textarea = await block.query_selector('textarea')
        short_input = await block.query_selector('input[type="text"]')

        if radios:
            q_type = "radio"
            options = []
            for r in radios:
                label = await r.get_attribute("aria-label")
                if label:
                    options.append(label)
        elif checkboxes:
            q_type = "checkbox"
            options = []
            for c in checkboxes:
                label = await c.get_attribute("aria-label")
                if label:
                    options.append(label)
        elif dropdown:
            q_type = "dropdown"
            options = []
            items = await block.query_selector_all('[role="option"]')
            for item in items:
                t = (await item.inner_text()).strip()
                if t:
                    options.append(t)
        elif textarea:
            q_type = "paragraph"
            options = []
        elif short_input:
            q_type = "short_answer"
            options = []
        else:
            continue

        questions.append(Question(
            index=i,
            text=text,
            question_type=q_type,
            options=options,
            image_base64=image_base64,
        ))

    print(f"解析到 {len(questions)} 道題目")
    return questions
