# chat2tasks

Turn an exported **WhatsApp** or **Telegram** chat into an organized task list.
Understands **Arabic (including Levantine/Gulf dialect)** and English. No dependencies, runs fully offline by default.

> حوّل محادثات واتساب وتلغرام إلى مهام منظمة: مين طلب شو، ومتى، وهل هو عاجل.

## Quick start

```bash
git clone https://github.com/AHMED-HUSSAM-10/chat2tasks
cd chat2tasks
python3 chat2tasks.py examples/sample_whatsapp.txt
```

Example output:

```markdown
# Tasks (5)

## 🔴 High priority
- [ ] ابعتلي ملف العميل اليوم ضروري — **اليوم** · from Sara · 12/11/2026

## Normal
- [ ] لازم نخلص عرض الأسعار بكرة الساعة 3 — **بكرة** · from Sara · 12/11/2026
- [ ] Please send the invoice to the client by Friday — **by Friday** · from Omar · 12/11/2026
```

Or install it as a command: `pip install .` then `chat2tasks chat.txt`.

## Getting your chat file

- **WhatsApp:** open the chat → ⋮ / contact name → *Export chat* → *Without media*. You get a `.txt` file.
- **Telegram Desktop:** open the chat → ⋮ → *Export chat history* → format **JSON**. Use the `result.json`.

## Usage

```
chat2tasks FILE [-f md|json|csv] [-o OUTPUT] [--sender NAME] [--min-score N] [--ai] [--model MODEL]
```

| Option | What it does |
|---|---|
| `-f, --format` | `md` (default, checkbox list), `json`, or `csv` |
| `-o, --output` | Write to a file instead of the terminal |
| `--sender` | Only look at messages from one person (substring match) |
| `--min-score` | Detection threshold. Lower (1) finds more tasks, higher (3) is stricter |
| `--ai` | Use the Anthropic API for smarter extraction (see below) |

## How it works

Default mode is rule-based. Each message gets a score:

- strong markers (`لازم`, `ضروري`, `لا تنسى`, `must`, `don't forget`, `deadline`…) → +2
- action verbs (`ابعت`, `راجع`, `جهز`, `send`, `book`, `review`…) → +2
- soft requests (`بدي`, `محتاج`, `ممكن`, `please`) → +1
- a deadline (`بكرة`, `يوم الخميس`, `الساعة 3`, `tomorrow`, `by Friday`…) → +1
- a question mark → −1

A message with score ≥ 2 becomes a task. It is marked **high** priority if it sounds urgent
(`عاجل`, `ضروري`, `asap`) or is due today.

It is a heuristic, so expect a few misses and false positives. Use `--min-score` to tune it,
or use `--ai`.

## AI mode (optional)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
chat2tasks chat.txt --ai -f json
```

**Privacy:** `--ai` sends the chat text to the Anthropic API. The default mode never leaves your machine.
Only the last ~60,000 characters of the chat are sent. Change the model with `--model` or `CHAT2TASKS_MODEL`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Roadmap

- [ ] Telegram bot mode (live, instead of exports)
- [ ] Export to Notion / Todoist / Google Tasks
- [ ] More dialect keywords (Egyptian, Maghrebi)

PRs welcome, especially new keywords for your dialect (see the lists at the top of `chat2tasks.py`).

## License

MIT © AHMED HUSSAM
