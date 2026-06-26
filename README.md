# test-helper

Automatically logs into a Google account, opens a given Google Form, answers it with Gemini, and fills it in.
Built mainly for multiple-choice forms, with support for image-based questions (handled via Gemini's vision).

> ⚠️ This tool is for personal learning and automation research only. Do not use it in ways that violate exam rules or academic integrity.

## Features

- Logs into Google in a background browser via Playwright (and remembers the session, so no repeated logins)
- Parses every question in the form (text, question type, options, images)
- Generates answers with Gemini (text and image questions handled uniformly)
- Fills in single-choice / multiple-choice / dropdown / short-answer questions
- **Does not auto-submit** — waits for you to confirm, then press Enter to close

## Install

Requires [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```
GOOGLE_EMAIL=your-google-email
GOOGLE_PASSWORD=your-google-password
GEMINI_API_KEY=your-gemini-api-key
```

- Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
- The free tier has a daily request limit (~20). For many questions, upgrade to a paid plan in AI Studio.

## Usage

```bash
uv run python main.py --url "https://docs.google.com/forms/d/e/xxxxx/viewform"
```

Flow: log in (or reuse saved session) → parse questions → answer with Gemini → fill the form → wait for Enter to close the browser.

## Project Structure

| File | Description |
|------|-------------|
| `main.py` | CLI entry point; wires the whole pipeline together |
| `google_auth.py` | Logs into Google via Playwright and saves the session to `auth_state/` |
| `form_parser.py` | Parses form questions (text + image screenshots) |
| `ai_solver.py` | Calls Gemini to generate answers |
| `form_filler.py` | Fills the answers into the form |

## Notes

- The login session is stored in `auth_state/` (gitignored) and re-authenticates automatically when it expires.
- If the account has 2FA or extra security checks, manual intervention may be required.
- The form is **not submitted by default**, so you can review the answers first. To auto-submit, edit the end of `form_filler.py`.
- CSS selectors follow the current Google Forms DOM; they may need updating if Google changes its markup.
