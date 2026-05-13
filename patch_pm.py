with open("ihm/main_window.py", "r", encoding="utf-8") as f:
    code = f.read()

panneau_haut_code = """
class PanneauHaut(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(270)
        self.setStyleSheet("background:#1f1f1f;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        self._result_badge = QLabel("---")
        self._result_badge.setFixedHeight(70)
        self._result_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._result_badge)
        
        self._counters_widget = QWidget()
        self._counters_widget.setFixedHeight(35)
        c_layout = QHBoxLayout(self._counters_widget)
        c_layout.setContentsMargins(0, 0, 0, 0)
        self._lbl_count_ok = QLabel("✓ 0")
        self._lbl_count_ok.setStyleSheet("color: #1D9E75; font-size: 14px; font-weight: bold;")
        self._lbl_count_nok = QLabel("✗ 0")
        self._lbl_count_nok.setStyleSheet("color: #E24B4A; font-size: 14px; font-weight: bold;")
        self._lbl_count_tot = QLabel("Σ 0")
        self._lbl_count_tot.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        c_layout.addWidget(self._lbl_count_ok)
        c_layout.addWidget(self._lbl_count_nok)
        c_layout.addWidget(self._lbl_count_tot)
        layout.addWidget(self._counters_widget)
        
        info_widget = QWidget()
        info_widget.setFixedHeight(30)
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        self._lbl_timestamp = QLabel("00:00:00")
        self._lbl_timestamp.setStyleSheet("color: #666666; font-size: 10px;")
        self._btn_pm = QPushButton("PM-01")
        self._btn_pm.setFixedSize(80, 26)
        info_layout.addWidget(self._lbl_timestamp)
        info_layout.addStretch()
        info_layout.addWidget(self._btn_pm)
        layout.addWidget(info_widget)
        
        fmax_widget = QWidget()
        fmax_widget.setFixedHeight(28)
        fmax_layout = QHBoxLayout(fmax_widget)
        fmax_layout.setContentsMargins(0, 0, 0, 0)
        lbl_ftext = QLabel("Fmax")
        lbl_ftext.setStyleSheet("color: #666666; font-size: 10px;")
        self._lbl_fmax = QLabel("0.0 N")
        self._lbl_fmax.setStyleSheet("color: #378ADD; font-size: 13px; font-weight: bold;")
        fmax_layout.addWidget(lbl_ftext)
        fmax_layout.addStretch()
        fmax_layout.addWidget(self._lbl_fmax)
        layout.addWidget(fmax_widget)
        
        xmax_widget = QWidget()
        xmax_widget.setFixedHeight(28)
        xmax_layout = QHBoxLayout(xmax_widget)
        xmax_layout.setContentsMargins(0, 0, 0, 0)
        lbl_xtext = QLabel("Xmax")
        lbl_xtext.setStyleSheet("color: #666666; font-size: 10px;")
        self._lbl_xmax = QLabel("0.0 mm")
        self._lbl_xmax.setStyleSheet("color: #378ADD; font-size: 13px; font-weight: bold;")
        xmax_layout.addWidget(lbl_xtext)
        xmax_layout.addStretch()
        xmax_layout.addWidget(self._lbl_xmax)
        layout.addWidget(xmax_widget)
        self.update_result(None)

    def update_result(self, ok: bool | None) -> None:
        if ok is True:
            self._result_badge.setStyleSheet("background: #085041; color: #4ade80; font-size: 36px; font-weight: bold;")
            self._result_badge.setText("OK")
        elif ok is False:
            self._result_badge.setStyleSheet("background: #791F1F; color: #E24B4A; font-size: 36px; font-weight: bold;")
            self._result_badge.setText("NOK")
        else:
            self._result_badge.setStyleSheet("background: #2a2a2a; color: #888888; font-size: 36px; font-weight: bold;")
            self._result_badge.setText("---")

    def update_counters(self, ok: int, nok: int, total: int) -> None:
        self._lbl_count_ok.setText(f"✓ {ok}")
        self._lbl_count_nok.setText(f"✗ {nok}")
        self._lbl_count_tot.setText(f"Σ {total}")

    def update_fmax(self, val: str) -> None:
        self._lbl_fmax.setText(val)

    def update_xmax(self, val: str) -> None:
        self._lbl_xmax.setText(val)

class MainWindow(QMainWindow):
"""

code = code.replace("class MainWindow(QMainWindow):", panneau_haut_code)

with open("ihm/main_window.py", "w", encoding="utf-8") as f:
    f.write(code)
