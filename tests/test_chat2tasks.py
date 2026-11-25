import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chat2tasks as c  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_whatsapp.txt")


class Tests(unittest.TestCase):
    def setUp(self):
        self.tasks = c.extract_rules(c.load_messages(SAMPLE))
        self.titles = [t.title for t in self.tasks]

    def test_detects_arabic_and_english(self):
        joined = "\n".join(self.titles)
        for needle in ["عرض الأسعار", "ملف العميل", "الشعار الجديد", "invoice", "meeting room", "تراجع"]:
            self.assertIn(needle, joined)

    def test_ignores_chitchat(self):
        joined = "\n".join(self.titles)
        for needle in ["قهوة", "كيف الحال", "رأيك", "Media"]:
            self.assertNotIn(needle, joined)

    def test_due_and_priority(self):
        by = {t.title: t for t in self.tasks}
        urgent = next(t for t in self.tasks if "ملف العميل" in t.title)
        self.assertEqual(urgent.priority, "high")
        self.assertTrue(next(t for t in self.tasks if "invoice" in t.title).due.lower().endswith("friday"))
        self.assertTrue(by)

    def test_telegram(self):
        data = {"messages": [
            {"type": "message", "date": "2026-11-12T10:00:00", "from": "Sara",
             "text": ["لازم ", {"type": "bold", "text": "نجهز"}, " التقرير بكرة"]},
            {"type": "service", "text": ""},
        ]}
        tasks = c.extract_rules(c.parse_telegram(data))
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].due, "بكرة")


if __name__ == "__main__":
    unittest.main()
