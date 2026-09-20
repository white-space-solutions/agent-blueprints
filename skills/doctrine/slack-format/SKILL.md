---
name: slack-format
description: "How to format text correctly for Slack's mrkdwn renderer (not Markdown). Encodes the full Slack-supported syntax subset \u2014 bold, italic, strike, code, quotes, bullets, links \u2014 and the Markdown constructs Slack does NOT support, so any Slack message composed by an agent renders cleanly instead of showing literal markdown characters."
when_to_use: "Before sending, editing, or scheduling ANY Slack message \u2014 to convert the message body into Slack mrkdwn syntax so it renders cleanly instead of showing literal markdown"
tags: ["slack","mrkdwn","formatting","markdown","messages"]
auth: none
---
# Slack Formatting (mrkdwn)

Slack renders a **mrkdwn** subset, not standard Markdown. Compose every Slack message with these rules or the output shows literal characters.

## Supported syntax — use these

| Intent | Slack syntax | Notes |
|--------|--------------|-------|
| Bold | `*text*` | single asterisk |
| Italic | `_text_` | underscore |
| Strikethrough | `~text~` | tilde |
| Inline code | `` `code` `` | single backtick |
| Code block | triple backticks ` ``` ` on its own lines | fenced |
| Quote | `> text` | `>` prefix |
| Bullets | `• text` (U+2022) | NOT a `-` dash |
| Numbered list | `1. text`, `2. text` | number + period + space |
| Links | `[label](url)` | the Slack send tool auto-converts to `<url\|label>`; do not hand-roll |

## NOT supported — do not use

- `#`, `##`, `###` headings (Slack ignores them; the hashes show literally)
- `**double**` bold (renders as literal asterisks in some clients)
- `- ` dash bullets (use `•` instead)
- `***bold italic***` triple asterisks
- Markdown tables (no pipe-table rendering)

For a "heading" effect, write the line in `*bold*` followed by a newline.

## Links and placeholders are handled for you

- `[label](url)` markdown links are auto-converted to Slack `<url|label>` by the send tool. Emit plain markdown links.
- `[[ARTIFACT_xxx]]` placeholders are auto-resolved to public URLs. Emit them as-is; do not construct URLs.

## Compose-then-send checklist

1. Bold is single-asterisk `*x*`, italics underscore `_x_`.
2. Bullets are `•`, not `-`.
3. No `#` headings — use bold line + newline.
4. Links are `[label](url)`, not raw or hand-rolled `<...|...>`.
5. Apply the no-em-dash / no-AI-speak copy rule to any prospect-facing Slack text.

## When to use

Any time an agent posts, edits, or schedules a Slack message (SlackBotSendMessage, SlackBotUpdateMessage, SlackBotScheduleMessage), including daily lead reports, draft-approval posts, #leads summaries, and DMs.
