"""Graphit-Look für Creative Notes (Farben wie in der Creative Shell)."""

import os
from pathlib import Path

C = {
    "ground": "#12151b",
    "surface": "#1c2029",
    "footer": "#171a22",
    "raised": "#232836",
    "editor": "#161920",
    "gutter": "#161920",
    "linenum": "#4d5568",
    "curline": "#1e222c",
    "text": "#dce6ff",
    "muted": "#9aa6c2",
    "comment": "#6f7a92",
    "accent": "#8fb3ff",
    "accentText": "#12151b",
    "flame": "#ffb07a",
    "teal": "#6fdcc0",
    "purple": "#d7a8ff",
    "yellow": "#f2d58a",
    "blue2": "#b9c9ff",
    "hit": "#5a4a22",
    "same": "#2c3650",
    "bracket": "#33405e",
    "badbracket": "#5c2a30",
    "selection": "#2f4675",
    "hairline": "rgba(255,255,255,0.07)",
    "hover": "rgba(255,255,255,0.07)",
    "pressed": "rgba(255,255,255,0.12)",
}


def icon_dir():
    for d in (Path(__file__).resolve().parent.parent.parent / "shell" / "creative_shell" / "qml" / "Creative" / "icons",
              Path("/usr/lib/creative-shell/creative_shell/qml/Creative/icons")):
        if d.is_dir():
            return d
    return None


def icon_path(name):
    d = icon_dir()
    if d and (d / f"{name}.svg").exists():
        return str(d / f"{name}.svg")
    return ""


def stylesheet():
    chevron = icon_path("chevron-down").replace(os.sep, "/")
    close = icon_path("close").replace(os.sep, "/")
    return f"""
* {{ font-family: "Arial", "Liberation Sans"; font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#central {{ background: {C['ground']}; }}
QToolTip {{ background: {C['raised']}; color: {C['text']}; border: 1px solid {C['hairline']}; border-radius: 8px; padding: 6px 9px; }}

/* Menüleiste */
QMenuBar {{ background: {C['footer']}; padding: 4px 8px 0 8px; }}
QMenuBar::item {{ background: transparent; padding: 6px 11px; border-radius: 8px; }}
QMenuBar::item:selected {{ background: {C['hover']}; }}
QMenuBar::item:pressed {{ background: {C['pressed']}; }}
QMenu {{ background: {C['raised']}; border: 1px solid {C['hairline']}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 14px; border-radius: 7px; }}
QMenu::item:selected {{ background: {C['hover']}; }}
QMenu::item:disabled {{ color: {C['comment']}; }}
QMenu::separator {{ height: 1px; background: {C['hairline']}; margin: 5px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; margin-left: 6px; }}
QMenu::indicator:checked {{ background: {C['accent']}; border-radius: 4px; }}
QMenu::right-arrow {{ width: 10px; height: 10px; }}

/* Werkzeugleiste */
QWidget#toolbar {{ background: {C['footer']}; }}
QToolButton {{ background: transparent; border: none; border-radius: 9px; padding: 6px; }}
QToolButton:hover {{ background: {C['hover']}; }}
QToolButton:pressed {{ background: {C['pressed']}; }}
QToolButton:checked {{ background: rgba(143,179,255,0.18); }}
QFrame#tsep {{ background: {C['hairline']}; }}

/* Reiter */
QTabWidget::pane {{ border: none; background: {C['editor']}; }}
QTabBar {{ background: {C['footer']}; qproperty-drawBase: 0; }}
QTabBar::tab {{ background: transparent; color: {C['muted']}; padding: 8px 10px 8px 14px; margin: 4px 2px 0 0;
               border-top-left-radius: 10px; border-top-right-radius: 10px; min-width: 70px; max-width: 240px; }}
QTabBar::tab:hover {{ background: rgba(255,255,255,0.04); color: {C['text']}; }}
QTabBar::tab:selected {{ background: {C['editor']}; color: {C['text']}; font-weight: bold; }}
QTabBar::close-button {{ image: url({close}); subcontrol-position: right; width: 12px; height: 12px; padding: 2px; border-radius: 5px; }}
QTabBar::close-button:hover {{ background: {C['pressed']}; }}
QTabBar QToolButton {{ background: {C['footer']}; border-radius: 6px; }}
QTabWidget QToolButton#plus {{ margin: 4px 6px 0 4px; }}

/* Editor */
QPlainTextEdit {{ background: {C['editor']}; color: {C['text']}; border: none;
                  selection-background-color: {C['selection']}; selection-color: {C['text']}; }}

/* Bildlaufleisten */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: rgba(255,255,255,0.16); border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: rgba(255,255,255,0.26); }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Suchleiste */
QWidget#findbar {{ background: {C['footer']}; border-top: 1px solid {C['hairline']}; }}
QLineEdit {{ background: {C['ground']}; border: 1px solid {C['hairline']}; border-radius: 9px; padding: 6px 10px;
            selection-background-color: {C['selection']}; }}
QLineEdit:focus {{ border-color: {C['accent']}; }}
QLineEdit[bad="true"] {{ border-color: {C['flame']}; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid rgba(255,255,255,0.25); background: {C['ground']}; }}
QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
QPushButton {{ background: rgba(255,255,255,0.07); border: none; border-radius: 9px; padding: 7px 14px; }}
QPushButton:hover {{ background: rgba(255,255,255,0.11); }}
QPushButton:pressed {{ background: rgba(255,255,255,0.15); }}
QPushButton:default, QPushButton[primary="true"] {{ background: {C['accent']}; color: {C['accentText']}; font-weight: bold; }}
QPushButton:disabled {{ color: {C['comment']}; }}
QLabel#count {{ color: {C['muted']}; }}

/* Statusleiste */
QStatusBar {{ background: {C['footer']}; border-top: 1px solid {C['hairline']}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {C['muted']}; padding: 2px 10px; font-size: 12px; }}
QStatusBar QToolButton {{ color: {C['muted']}; font-size: 12px; padding: 2px 10px; border-radius: 6px; }}
QStatusBar QToolButton::menu-indicator {{ image: none; width: 0; }}

/* Dialoge */
QDialog, QMessageBox, QInputDialog {{ background: {C['surface']}; }}
QMessageBox QLabel {{ font-size: 13px; }}
QComboBox {{ background: {C['ground']}; border: 1px solid {C['hairline']}; border-radius: 9px; padding: 6px 10px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {C['raised']}; border: 1px solid {C['hairline']}; selection-background-color: {C['hover']}; }}
QSpinBox {{ background: {C['ground']}; border: 1px solid {C['hairline']}; border-radius: 9px; padding: 6px 10px; }}
"""
