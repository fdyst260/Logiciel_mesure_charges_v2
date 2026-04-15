import re
with open("ihm/main_window.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix btn_pm CSS
text = re.sub(
    r"QPushButton#btn_pm \{\{\s*background-color:.*?padding: 6px;\s*\}\}",
    r"QPushButton#btn_pm {{\n    background-color: {COLORS['bg_button']};\n    color: {COLORS['text_primary']};\n    font-size: 12px;\n    font-weight: bold;\n    border: 1px solid {COLORS['border']};\n    border-radius: 4px;\n    padding: 2px 4px;\n    text-align: left;\n}}",
    text,
    flags=re.DOTALL
)

text = re.sub(
    r"QPushButton#btn_pm \{\{\s*background-color: \{c\['bg_button'\].*?padding: 6px;\s*\}\}",
    r"QPushButton#btn_pm {{\n    background-color: {c['bg_button']};\n    color: {c['text_primary']};\n    font-size: 12px;\n    font-weight: bold;\n    border: 1px solid {c['border']};\n    border-radius: 4px;\n    padding: 2px 4px;\n    text-align: left;\n}}",
    text,
    flags=re.DOTALL
)

# Fix datetime CSS? Let's check datetime_label
if "QLabel#datetime_label" not in text:
    text = text.replace("STYLESHEET = f\"\"\"", "STYLESHEET = f\"\"\"\nQLabel#datetime_label {{ font-size: 11px; color: {COLORS['text_secondary']}; }}")
    text = text.replace("new_stylesheet = f\"\"\"", "new_stylesheet = f\"\"\"\nQLabel#datetime_label {{ font-size: 11px; color: {c['text_secondary']}; }}")

with open("ihm/main_window.py", "w", encoding="utf-8") as f:
    f.write(text)
