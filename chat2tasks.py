#!/usr/bin/env python3
"""chat2tasks - turn an exported WhatsApp / Telegram chat into a task list.

Works offline with no dependencies (rule-based, Arabic + English).
Optional --ai mode uses the Anthropic API for better results.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date

__version__ = "0.1.0"
__author__ = "AHMED HUSSAM"


@dataclass
class Message:
    date: str
    sender: str
    text: str


@dataclass
class Task:
    title: str
    sender: str
    date: str
    due: str = ""
    priority: str = "normal"  # "high" | "normal"


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

_WA_HEADER = re.compile(
    r"^\[?(?P<date>\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap]\.?[Mm]\.?)?)\]?\s*(?:-\s*)?(?P<rest>.*)$"
)
_WA_SENDER = re.compile(r"^(?P<sender>[^:]{1,80}?):\s(?P<text>.*)$")
_WA_SKIP = re.compile(
    r"omitted|<attached:|تم حذف هذه الرسالة|this message was deleted|"
    r"الوسائط مستبعدة|صورة محذوفة|^<.*>$",
    re.IGNORECASE,
)


def parse_whatsapp(raw):
    """Parse a WhatsApp 'Export chat' .txt file (Android or iOS)."""
    messages, cur = [], None
    for line in raw.splitlines():
        line = line.lstrip("\u200e\u200f\u202a\ufeff")
        head = _WA_HEADER.match(line)
        if head:
            if cur:
                messages.append(cur)
            cur = None
            who = _WA_SENDER.match(head.group("rest"))
            if who:  # no sender => system message ("Messages are encrypted...")
                cur = Message(head.group("date"), who.group("sender").strip(), who.group("text"))
        elif cur is not None:
            cur.text += "\n" + line
    if cur:
        messages.append(cur)
    return [m for m in messages if m.text.strip() and not _WA_SKIP.search(m.text.strip())]


def _tg_text(value):
    if isinstance(value, str):
        return value
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in value)


def parse_telegram(data):
    """Parse Telegram Desktop 'Export chat history' result.json."""
    raw_msgs = data.get("messages")
    if raw_msgs is None and "chats" in data:  # full-account export
        raw_msgs = [m for c in data["chats"]["list"] for m in c.get("messages", [])]
    out = []
    for m in raw_msgs or []:
        if m.get("type") != "message":
            continue
        text = _tg_text(m.get("text", "")).strip()
        if text:
            out.append(Message(str(m.get("date", ""))[:10], m.get("from") or "?", text))
    return out


def load_messages(path):
    with open(path, encoding="utf-8-sig") as f:
        raw = f.read()
    if path.lower().endswith(".json"):
        return parse_telegram(json.loads(raw))
    return parse_whatsapp(raw)


# --------------------------------------------------------------------------
# Rule-based task detection (Arabic incl. Levantine/Gulf dialect + English)
# --------------------------------------------------------------------------

_LETTER_CLASS = {"ا": "[اأإآ]", "ي": "[يى]", "ى": "[يى]", "ه": "[هة]", "ة": "[هة]"}
_DIACRITICS = re.compile(r"[\u0640\u064B-\u065F\u0670]")


def _ar(word):
    return r"\s+".join("".join(_LETTER_CLASS.get(c, re.escape(c)) for c in w) for w in word.split())


def _ar_re(words, suffixes=True):
    alt = "|".join(_ar(w) for w in words)
    suf = r"(?:ني|لي|لنا|نا|ها|هم|ه|ك|كم|وا)*" if suffixes else ""
    return re.compile(r"(?<!\w)[وفبل]?(?:" + alt + ")" + suf + r"(?!\w)")


def _en_re(words, start_only=False):
    alt = "|".join(re.escape(w) for w in words)
    prefix = r"^(?:please\s+|pls\s+|can you\s+|could you\s+)?" if start_only else r"\b"
    return re.compile(prefix + "(?:" + alt + r")\b", re.IGNORECASE)


DAYS_AR = ["الاحد", "الاثنين", "الثلاثاء", "الاربعاء", "الخميس", "الجمعة", "السبت"]
DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

STRONG_AR = _ar_re(["لازم", "ضروري", "لا تنسى", "لا تنسوا", "ما تنسى", "ما تنسوا",
                    "ذكرني", "مطلوب", "اهم شي"])
STRONG_EN = _en_re(["todo", "to-do", "don't forget", "dont forget", "remember to", "must",
                    "need to", "needs to", "have to", "deadline", "action item"])
ACTION_AR = _ar_re(["ابعت", "ابعث", "ارسل", "جهز", "راجع", "تاكد", "كلم", "اتصل", "احجز",
                    "ادفع", "سدد", "سلم", "عدل", "اعمل", "سوي", "جيب", "اشتري", "رتب",
                    "حضر", "ارفع", "حدث", "ضيف", "صلح", "اكتب", "حدد", "تبعت", "ترسل",
                    "تجهز", "تراجع", "تتاكد", "تكلم", "اتاكد", "اتصل"])
ACTION_EN = _en_re(["send", "call", "book", "pay", "review", "finish", "submit", "prepare",
                    "update", "fix", "check", "schedule", "email", "buy", "share", "confirm",
                    "create", "write", "upload", "reply"], start_only=True)
WEAK_AR = _ar_re(["بدي", "بدنا", "محتاج", "محتاجين", "لو سمحت", "يا ريت", "ممكن"])
WEAK_EN = _en_re(["please", "pls", "can you", "could you"])
URGENT = re.compile(
    _ar_re(["عاجل", "مستعجل", "فورا", "حالا", "هلق", "ضروري"], suffixes=False).pattern
    + r"|\b(?:urgent|asap|immediately|right now)\b",
    re.IGNORECASE,
)

_TIME_AR = r"(?:\s*(?:صباحا|مساء|ظهرا|الصبح|العصر))?"
DUE = re.compile(
    "|".join([
        r"(?<!\w)(?:قبل |لحد |ب)?(?:" + "|".join(_ar(w) for w in [
            "اليوم", "بكرة", "بكرا", "غدا", "الليلة", "بعد بكرة", "اخر الاسبوع",
            "نهاية الاسبوع", "الاسبوع الجاي", "الاسبوع القادم", "الشهر الجاي",
            "الشهر القادم"]) + r")(?!\w)",
        r"(?<!\w)(?:قبل |لحد )?يوم\s+(?:" + "|".join(_ar(d) for d in DAYS_AR) + r")(?!\w)",
        r"(?<!\w)(?:قبل |لحد )?الساعة\s*\d{1,2}(?::\d{2})?" + _TIME_AR,
        r"\b(?:today|tonight|tomorrow|next week|next month|eod|eow|end of (?:the )?(?:day|week|month))\b",
        r"\b(?:on |by |before |next )?(?:" + "|".join(DAYS_EN) + r")\b",
        r"\b(?:by|before|at) \d{1,2}(?::\d{2})?\s?(?:am|pm)?\b",
        r"\b\d{1,2}\s?(?:am|pm)\b",
        r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
    ]),
    re.IGNORECASE,
)
_TODAY = re.compile(
    "|".join([_ar(w) for w in ["اليوم", "الليلة"]]) + r"|\b(?:today|tonight|eod)\b", re.IGNORECASE
)


def _clean(text):
    return _DIACRITICS.sub("", text)


def _score(text):
    """Return (score, due, priority) for one message."""
    t = _clean(text)
    score = 0
    if STRONG_AR.search(t) or STRONG_EN.search(t):
        score += 2
    if ACTION_AR.search(t) or ACTION_EN.search(t.strip()):
        score += 2
    if WEAK_AR.search(t) or WEAK_EN.search(t):
        score += 1
    due_m = DUE.search(t)
    if due_m:
        score += 1
    if t.rstrip().endswith(("?", "؟")) and score < 3:
        score -= 1
    due = due_m.group(0).strip() if due_m else ""
    high = bool(URGENT.search(t)) or bool(due and _TODAY.search(due))
    return score, due, "high" if high else "normal"


def extract_rules(messages, sender=None, min_score=2):
    tasks, seen = [], set()
    for m in messages:
        if sender and sender.lower() not in m.sender.lower():
            continue
        for part in re.split(r"\n+", m.text):  # one chat bubble may hold several asks
            part = " ".join(part.split())
            if len(part.split()) < 2:
                continue
            score, due, prio = _score(part)
            key = _clean(part).lower()
            if score >= min_score and key not in seen:
                seen.add(key)
                tasks.append(Task(part, m.sender, m.date, due, prio))
    return tasks


# --------------------------------------------------------------------------
# Optional AI mode (Anthropic API, standard library only)
# --------------------------------------------------------------------------

AI_PROMPT = """Below is a chat export. Extract the actionable tasks (things someone must do).
Ignore small talk. Keep each task in the language it was written in.
Reply with ONLY a JSON array; each item has the keys:
"title" (short, imperative), "sender" (who asked), "date" (message date),
"due" (deadline if mentioned, else ""), "priority" ("high" or "normal").

Chat:
{chat}"""


def extract_ai(messages, model, max_chars=60000):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("error: set ANTHROPIC_API_KEY to use --ai")
    chat = "\n".join(f"[{m.date}] {m.sender}: {m.text}" for m in messages)[-max_chars:]
    body = json.dumps({
        "model": model,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": AI_PROMPT.format(chat=chat)}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
    except urllib.error.URLError as e:
        sys.exit(f"error: API request failed: {e}")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    found = re.search(r"\[.*\]", text, re.S)
    if not found:
        sys.exit("error: model did not return a JSON array")
    tasks = []
    for item in json.loads(found.group(0)):
        prio = "high" if str(item.get("priority", "")).lower() == "high" else "normal"
        tasks.append(Task(str(item.get("title", "")).strip(), str(item.get("sender", "")),
                          str(item.get("date", "")), str(item.get("due", "")), prio))
    return [t for t in tasks if t.title]


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def render_markdown(tasks, source):
    lines = [f"# Tasks ({len(tasks)})", "", f"Source: `{source}` · generated {date.today()}", ""]
    for prio, label in (("high", "🔴 High priority"), ("normal", "Normal")):
        group = [t for t in tasks if t.priority == prio]
        if not group:
            continue
        lines += [f"## {label}", ""]
        for t in group:
            extra = [f"**{t.due}**"] if t.due else []
            extra.append(f"from {t.sender}")
            if t.date:
                extra.append(t.date)
            lines.append(f"- [ ] {t.title} — " + " · ".join(extra))
        lines.append("")
    return "\n".join(lines)


def render_csv(tasks):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["title", "sender", "date", "due", "priority"])
    w.writeheader()
    w.writerows(asdict(t) for t in tasks)
    return buf.getvalue()


def render(tasks, fmt, source):
    if fmt == "json":
        return json.dumps([asdict(t) for t in tasks], ensure_ascii=False, indent=2)
    if fmt == "csv":
        return render_csv(tasks)
    return render_markdown(tasks, source)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="chat2tasks",
        description="Turn an exported WhatsApp (.txt) or Telegram (result.json) chat into tasks.")
    p.add_argument("file", help="WhatsApp .txt export or Telegram result.json")
    p.add_argument("-f", "--format", choices=["md", "json", "csv"], default="md")
    p.add_argument("-o", "--output", help="write to a file instead of stdout")
    p.add_argument("--sender", help="only messages from this sender (substring match)")
    p.add_argument("--min-score", type=int, default=2,
                   help="detection threshold, lower = more tasks (default 2)")
    p.add_argument("--ai", action="store_true",
                   help="use the Anthropic API (sends chat text to the API)")
    p.add_argument("--model", default=os.environ.get("CHAT2TASKS_MODEL", "claude-sonnet-5-5"))
    p.add_argument("--version", action="version", version=__version__)
    args = p.parse_args(argv)

    messages = load_messages(args.file)
    if args.sender:
        messages = [m for m in messages if args.sender.lower() in m.sender.lower()]
    if args.ai:
        tasks = extract_ai(messages, args.model)
    else:
        tasks = extract_rules(messages, min_score=args.min_score)

    out = render(tasks, args.format, os.path.basename(args.file))
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        print(f"{len(tasks)} tasks -> {args.output}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
        print(out)


if __name__ == "__main__":
    main()
