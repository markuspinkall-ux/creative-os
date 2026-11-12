"""Graphit/Porzellan-Farben und Stylesheet der Creative Engine."""

from PySide6.QtGui import QColor

try:
    from creative_look import palette as _look_palette
except ImportError:
    _look_palette = None

GRAPHIT = {"ground": "#12151b", "surface": "#1c2029", "side": "#171a22", "raised": "#232836",
           "track": "#3a4252", "line": "#2a303d", "text": "#dce6ff", "muted": "#9aa6c4", "dim": "#6f7a92",
           "accent": "#8fb3ff", "accentText": "#12151b", "accentHover": "#a6c3ff", "select": "#2a3a5c",
           "flame": "#ffb07a", "ok": "#6fdcc0", "danger": "#ff8a8e", "view": "#161920"}


def colors():
    pal = dict(GRAPHIT)
    if _look_palette is not None:
        try:
            pal = _look_palette(pal)
        except Exception:
            pass
    pal["light"] = QColor(pal["ground"]).lightness() > 128
    return pal


C = colors()


def stylesheet():
    c = C
    return f"""
    QWidget {{ color:{c['text']}; font-size:13px; }}
    QMainWindow, QWidget#root {{ background:{c['ground']}; }}
    QWidget#topBar {{ background:{c['ground']}; }}
    QLabel {{ background:transparent; }}
    QLabel#appTitle {{ font-size:15px; font-weight:700; }}
    QLabel#projectName {{ color:{c['muted']}; font-size:13px; }}
    QLabel#heading {{ font-size:26px; font-weight:700; }}
    QLabel#sub, QLabel#muted {{ color:{c['muted']}; }}
    QLabel#section {{ color:{c['dim']}; font-size:11px; font-weight:700; letter-spacing:1px; }}
    QPushButton {{ background:{c['raised']}; color:{c['text']}; border:1px solid {c['line']}; border-radius:9px; padding:7px 14px; }}
    QPushButton:hover {{ border-color:{c['track']}; }}
    QPushButton:checked {{ background:{c['select']}; border-color:{c['accent']}; }}
    QPushButton:disabled {{ color:{c['dim']}; }}
    QPushButton#primary {{ background:{c['accent']}; color:{c['accentText']}; border:none; font-weight:700; }}
    QPushButton#primary:hover {{ background:{c['accentHover']}; }}
    QPushButton#ghost {{ background:transparent; border:none; }}
    QPushButton#ghost:hover {{ background:{c['raised']}; }}
    QToolButton {{ background:transparent; color:{c['text']}; border:1px solid transparent; border-radius:8px; padding:4px; }}
    QToolButton:hover {{ background:{c['raised']}; }}
    QToolButton:checked {{ background:{c['select']}; border-color:{c['accent']}; }}
    QToolButton::menu-indicator {{ image:none; width:0; }}
    QFrame#panel, QWidget#panel {{ background:{c['surface']}; border:1px solid {c['line']}; border-radius:14px; }}
    QWidget#side {{ background:{c['side']}; border-right:1px solid {c['line']}; }}
    QWidget#props {{ background:{c['side']}; border-left:1px solid {c['line']}; }}
    QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background:{c['raised']}; color:{c['text']};
        border:1px solid {c['line']}; border-radius:7px; padding:4px 7px; selection-background-color:{c['accent']};
        selection-color:{c['accentText']}; }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color:{c['accent']}; }}
    QComboBox QAbstractItemView {{ background:{c['raised']}; color:{c['text']}; selection-background-color:{c['select']}; }}
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width:0; border:none; }}
    QSlider::groove:horizontal {{ height:4px; background:{c['track']}; border-radius:2px; }}
    QSlider::handle:horizontal {{ background:{c['accent']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
    QListWidget {{ background:transparent; border:none; outline:none; }}
    QListWidget::item {{ border-radius:8px; padding:6px; }}
    QListWidget::item:hover {{ background:{c['raised']}; }}
    QListWidget::item:selected {{ background:{c['select']}; color:{c['text']}; }}
    QListWidget#timeline::item {{ background:{c['surface']}; border:1px solid {c['line']}; border-radius:12px; margin:4px; padding:8px; }}
    QListWidget#timeline::item:selected {{ background:{c['select']}; border:1px solid {c['accent']}; }}
    QMenu {{ background:{c['surface']}; color:{c['text']}; border:1px solid {c['line']}; border-radius:10px; padding:6px; }}
    QMenu::item {{ padding:6px 20px 6px 10px; border-radius:6px; }}
    QMenu::item:selected {{ background:{c['select']}; }}
    QMenu::separator {{ height:1px; background:{c['line']}; margin:5px 6px; }}
    QScrollBar:vertical {{ background:transparent; width:10px; }}
    QScrollBar::handle:vertical {{ background:{c['track']}; border-radius:4px; min-height:30px; }}
    QScrollBar:horizontal {{ background:transparent; height:10px; }}
    QScrollBar::handle:horizontal {{ background:{c['track']}; border-radius:4px; min-width:30px; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background:none; border:none; width:0; height:0; }}
    QGraphicsView {{ border:none; background:{c['view']}; }}
    QToolTip {{ background:{c['raised']}; color:{c['text']}; border:1px solid {c['line']}; border-radius:6px; padding:5px 8px; }}
    QProgressBar {{ background:{c['raised']}; border:none; border-radius:5px; height:10px; text-align:center; }}
    QProgressBar::chunk {{ background:{c['accent']}; border-radius:5px; }}
    QDialog {{ background:{c['surface']}; }}
    QCheckBox {{ spacing:8px; }}
    QPushButton#card {{ background:{c['surface']}; border:1px solid {c['line']}; border-radius:16px; text-align:left; padding:0; }}
    QPushButton#card:hover {{ border-color:{c['accent']}; }}
    QPushButton#card:disabled {{ background:{c['side']}; }}
    QWidget#statusBar {{ background:{c['ground']}; border-top:1px solid {c['line']}; }}
    QWidget#statusBar QLabel {{ color:{c['muted']}; font-size:12px; }}
    """
