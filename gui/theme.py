from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

_BASE_QSS = """
QPushButton {{
    border-radius: 18px;
    padding: 10px 28px;
    background: {button_bg};
    color: {text};
    border: 1px solid {border};
}}
QPushButton:hover {{
    background: {button_bg_hover};
}}
QPushButton[class~="primary"] {{
    border-radius: 18px;
    padding: 10px 28px;
    background: {accent};
    color: #ffffff;
    border: 1px solid transparent;
    font-weight: 600;
}}
QPushButton[class~="primary"]:hover {{
    background: {accent_hover};
}}
QPushButton[class~="secondary"] {{
    border-radius: 18px;
    padding: 10px 28px;
    background: transparent;
    color: {text};
    border: 1px solid {border};
}}
QPushButton[class~="secondary"]:hover {{
    background: {card_bg_hover};
}}
QFrame[class~="card"] {{
    background: {card_bg};
    border-radius: 14px;
    border: 1px solid {border};
}}
QFrame[class~="card"]:hover {{
    background: {card_bg_hover};
    border: 1px solid {accent};
}}
QLineEdit, QComboBox, QSpinBox {{
    border-radius: 8px;
    padding: 6px 10px;
    border: 1px solid {border};
    background: {input_bg};
    color: {text};
}}
QListWidget, QTableWidget, QTreeWidget {{
    border-radius: 8px;
    border: 1px solid {border};
    background: {input_bg};
    color: {text};
}}
QWidget {{
    background: {window_bg};
    color: {text};
}}
QLabel[class~="hint"] {{
    color: {muted_text};
}}
"""

_DARK_COLORS = dict(
    window_bg="#1e1f24", text="#e8e8ec", border="#3a3b42",
    button_bg="#2c2d34", button_bg_hover="#35363e",
    accent="#4f8ff7", accent_hover="#3f7de0",
    card_bg="#26272d", card_bg_hover="#2f3038", input_bg="#26272d",
    muted_text="#aeb0ba",  # heller als palette(mid) -- die App-eigene Grautönung war auf
                           # dunklem Grund kaum lesbar
)

_LIGHT_COLORS = dict(
    window_bg="#f5f5f7", text="#1c1c1e", border="#d4d4d9",
    button_bg="#ffffff", button_bg_hover="#ececef",
    accent="#3574f0", accent_hover="#2861d6",
    card_bg="#ffffff", card_bg_hover="#f0f0f3", input_bg="#ffffff",
    muted_text="#55565f",
)

DARK_QSS = _BASE_QSS.format(**_DARK_COLORS)
LIGHT_QSS = _BASE_QSS.format(**_LIGHT_COLORS)


def apply_theme(app: QApplication) -> None:
    # Native/Fallback-Stile (z.B. der hier verwendete "Windows"-Stil, falls
    # ein System-Stil wie GTK nicht verfügbar ist) rendern benutzerdefiniertes
    # QSS wie border-radius auf gefüllten Buttons unzuverlässig. Fusion ist
    # Qts eigener, plattformunabhängiger Stil mit vollständiger QSS-Unterstützung.
    app.setStyle("Fusion")
    is_dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    app.setStyleSheet(DARK_QSS if is_dark else LIGHT_QSS)
