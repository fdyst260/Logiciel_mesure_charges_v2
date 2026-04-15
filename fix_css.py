import re
with open("ihm/main_window.py", "r", encoding="utf-8") as f:
    text = f.read()

replacement = r"""QPushButton#btn_settings {
    background-color: #A07830;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: bold;
    border: 2px solid #7A5A20;
    border-radius: 8px;
    min-height: 36px;
    padding: 0 8px;
}
QPushButton#btn_settings:hover {
    background-color: #8B6520;
}
QPushButton#btn_settings:pressed {
    background-color: #6B4A10;
    padding-top: 2px;
}

QPushButton#nav_btn {
    background-color: #FAFAF8;
    color: #1A1A18;
    font-size: 14px;
    font-weight: 600;
    border: 1px solid #888480;
    border-radius: 6px;
    min-height: 48px;
    padding: 0 4px;
}
QPushButton#nav_btn:checked {
    background-color: #C49A3C;
    color: #FFFFFF;
    border: 1px solid #A07830;
}
QPushButton#nav_btn:pressed {
    background-color: #E8E4DC;
    padding-top: 2px;
}
QPushButton#nav_btn:checked:pressed {
    background-color: #8B6520;
}

QPushButton#nav_btn_red {
    background-color: #FFF3F3;
    color: #C62828;
    font-size: 14px;
    font-weight: 600;
    border: 1px solid #C62828;
    border-radius: 6px;
    min-height: 48px;
    padding: 0 4px;
}
QPushButton#nav_btn_red:pressed {
    background-color: #FFEBEE;
    padding-top: 2px;
}"""

replacement = replacement.replace("{", "{{").replace("}", "}}")

# find QPushButton#btn_settings down to """
pattern = re.compile(r"QPushButton#btn_settings .*?\"\"\"", re.DOTALL)
new_text = pattern.sub(replacement + '\n"""', text)

with open("ihm/main_window.py", "w", encoding="utf-8") as f:
    f.write(new_text)

