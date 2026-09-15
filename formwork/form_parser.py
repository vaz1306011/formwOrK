from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field

from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class Question:
    index: int
    text: str
    question_type: (
        str  # "radio" | "checkbox" | "dropdown" | "short_answer" | "paragraph"
    )
    options: list[str] = field(default_factory=list)
    image_base64: str | None = None
    auto_answer: str | None = None
    context: str | None = None
    grid_row: int | None = None  # row index within a grid (matrix) question


async def parse_form(page: Page, url: str | None) -> list[Question]:
    if url:
        await page.goto(url, wait_until="networkidle")
    await page.wait_for_selector('[role="listitem"]', timeout=15000)

    question_blocks = await page.query_selector_all('[role="listitem"]')
    questions: list[Question] = []
    current_context: str | None = None
    current_context_image: str | None = None

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

        radiogroups = await block.query_selector_all('[role="radiogroup"]')
        checkbox_groups = await block.query_selector_all('[role="group"]')
        radios = await block.query_selector_all('[role="radio"]')
        checkboxes = await block.query_selector_all('[role="checkbox"]')
        dropdown = await block.query_selector('[role="listbox"]')
        textarea = await block.query_selector("textarea")
        short_input = await block.query_selector('input[type="text"]')

        if len(radiogroups) > 1:
            # multiple-choice grid: each radiogroup is one row
            if not image_base64 and current_context_image:
                image_base64 = current_context_image
            for row_idx, rg in enumerate(radiogroups):
                row_label = await rg.get_attribute("aria-label")
                row_radios = await rg.query_selector_all('[role="radio"]')
                row_options = []
                for r in row_radios:
                    label = await r.get_attribute("aria-label")
                    if label:
                        row_options.append(label)
                questions.append(
                    Question(
                        index=i,
                        text=f"{text}：{row_label or f'第{row_idx + 1}列'}",
                        question_type="radio",
                        options=row_options,
                        image_base64=image_base64,
                        context=current_context,
                        grid_row=row_idx,
                    )
                )
            continue
        elif len(checkbox_groups) > 1 and any(
            await g.query_selector('[role="checkbox"]') for g in checkbox_groups
        ):
            # checkbox grid: each group is one row
            if not image_base64 and current_context_image:
                image_base64 = current_context_image
            for row_idx, g in enumerate(checkbox_groups):
                row_label = await g.get_attribute("aria-label")
                row_checkboxes = await g.query_selector_all('[role="checkbox"]')
                row_options = []
                for c in row_checkboxes:
                    label = await c.get_attribute("aria-label")
                    if label:
                        row_options.append(label)
                questions.append(
                    Question(
                        index=i,
                        text=f"{text}：{row_label or f'第{row_idx + 1}列'}",
                        question_type="checkbox",
                        options=row_options,
                        image_base64=image_base64,
                        context=current_context,
                        grid_row=row_idx,
                    )
                )
            continue
        elif radios:
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
            current_context = text
            current_context_image = image_base64
            continue

        if not image_base64 and current_context_image:
            image_base64 = current_context_image

        questions.append(
            Question(
                index=i,
                text=text,
                question_type=q_type,
                options=options,
                image_base64=image_base64,
                context=current_context,
            )
        )

    logger.info("解析到 %d 道題目", len(questions))
    return questions
