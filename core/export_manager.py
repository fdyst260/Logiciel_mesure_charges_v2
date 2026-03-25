"""Gestion des exports CSV et PDF vers clé USB.

Fonctions principales :
  - find_usb_drives()        : détecte les clés USB montées
  - export_csv_to_usb()      : copie les CSV filtrés vers ACM_Export/ sur la clé
  - generate_pdf_report()    : génère un rapport PDF de production (reportlab)
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class ExportWorker(QThread):
    """Worker thread pour les opérations d'export lourdes (PDF, USB, détection)."""

    task_done = Signal(bool, str)  # succès, message
    drives_detected = Signal(list)  # liste des points de montage

    def __init__(self, task: str, **kwargs) -> None:
        super().__init__()
        self._task = task
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            if self._task == "pdf":
                ok = generate_pdf_report(**self._kwargs)
                msg = "Rapport PDF généré." if ok else "Erreur génération PDF."
                self.task_done.emit(ok, msg)
            elif self._task == "usb":
                copied, skipped = export_csv_to_usb(**self._kwargs)
                self.task_done.emit(
                    True,
                    f"{copied} fichier(s) copié(s), {skipped} ignoré(s).",
                )
            elif self._task == "detect":
                drives = find_usb_drives()
                self.drives_detected.emit(drives)
                if drives:
                    self.task_done.emit(
                        True, f"{len(drives)} clé(s) : {', '.join(drives)}"
                    )
                else:
                    self.task_done.emit(False, "Aucune clé USB détectée")
        except Exception as e:
            self.task_done.emit(False, str(e))


def find_usb_drives() -> list[str]:
    """Retourne la liste des points de montage USB détectés.

    Sur Raspberry Pi, les clés USB sont montées dans /media/
    ou /mnt/ automatiquement par udisks2.
    """
    drives: list[str] = []
    for base in ["/media", "/mnt"]:
        if not os.path.exists(base):
            continue
        try:
            entries = os.listdir(base)
        except PermissionError:
            continue
        for entry in entries:
            full = os.path.join(base, entry)
            if not os.path.isdir(full):
                continue
            # Cas /media/CLEDRIVE directement (mountpoint)
            if os.path.ismount(full):
                drives.append(full)
                continue
            # Cas /media/username/CLEDRIVE
            try:
                sub_entries = os.listdir(full)
            except PermissionError:
                continue
            for sub in sub_entries:
                sub_path = os.path.join(full, sub)
                if os.path.isdir(sub_path) and os.path.ismount(sub_path):
                    drives.append(sub_path)
    return list(set(drives))


def export_csv_to_usb(
    source_dir: Path,
    usb_path: str,
    filter_result: str = "OK+NOK",
    pm_filter: int | None = None,
) -> tuple[int, int]:
    """Copie les fichiers CSV de source_dir vers usb_path/ACM_Export/<horodatage>/.

    filter_result : "OK+NOK" | "OK uniquement" | "NOK uniquement"
    pm_filter     : None = tous les PM, sinon numéro PM (1-16)

    Retourne (nb_copiés, nb_ignorés).
    """
    dest = (
        Path(usb_path)
        / "ACM_Export"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    dest.mkdir(parents=True, exist_ok=True)

    copied, skipped = 0, 0
    source_dir = Path(source_dir)
    if not source_dir.exists():
        return 0, 0

    for csv_file in source_dir.glob("*.csv"):
        name = csv_file.name.upper()

        # Filtrer par résultat
        if filter_result == "OK uniquement" and "NOK" in name:
            skipped += 1
            continue
        if filter_result == "NOK uniquement" and "PASS" in name:
            skipped += 1
            continue

        # Filtrer par PM
        if pm_filter is not None and f"PM{pm_filter:02d}" not in name:
            skipped += 1
            continue

        shutil.copy2(csv_file, dest / csv_file.name)
        copied += 1

    return copied, skipped


def generate_pdf_report(
    cycles_data: list[dict],
    output_path: Path,
    pm_name: str = "PM-01",
    machine_name: str = "ACM Riveteuse",
    periode: str = "Tout l'historique",
) -> bool:
    """Génère un rapport PDF de production.

    cycles_data : liste de dicts avec clés :
        cycle_num, fmax, xmax, result, timestamp, points (list of (pos, force))

    Utilise reportlab. Retourne True si succès.
    Structure du rapport :
      - Page 1 : En-tête + tableau récapitulatif de tous les cycles
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=20 * mm,
            bottomMargin=15 * mm,
        )
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=18,
            spaceAfter=6,
        )
        sub_style = ParagraphStyle(
            "Sub",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=12,
        )

        # En-tête
        story.append(
            Paragraph(f"Rapport de production — {machine_name}  |  {periode}", title_style)
        )
        story.append(
            Paragraph(
                f"Programme : {pm_name}  |  "
                f"Généré le : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  |  "
                f"Cycles : {len(cycles_data)}",
                sub_style,
            )
        )
        story.append(Spacer(1, 5 * mm))

        # Statistiques globales
        total = len(cycles_data)
        nb_ok = sum(1 for c in cycles_data if c.get("result") == "PASS")
        nb_nok = total - nb_ok
        taux = (nb_ok / total * 100) if total else 0.0

        stats_data = [
            ["Total cycles", "OK", "NOK", "Taux OK"],
            [str(total), str(nb_ok), str(nb_nok), f"{taux:.1f} %"],
        ]
        stats_table = Table(stats_data, colWidths=[45 * mm] * 4)
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#e3f2fd")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(stats_table)
        story.append(Spacer(1, 8 * mm))

        # Tableau détaillé
        story.append(Paragraph("Détail des cycles", styles["Heading2"]))
        table_data = [["Cycle", "Heure", "Fmax (N)", "Xmax (mm)", "Résultat"]]
        for c in cycles_data:
            result_str = "PASS" if c.get("result") == "PASS" else "NOK"
            table_data.append(
                [
                    str(c.get("cycle_num", "")),
                    c.get("timestamp", ""),
                    f"{c.get('fmax', 0):.0f}",
                    f"{c.get('xmax', 0):.1f}",
                    result_str,
                ]
            )

        col_widths = [20 * mm, 35 * mm, 35 * mm, 35 * mm, 35 * mm]
        detail_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        detail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f5f5f5")],
                    ),
                ]
            )
        )

        # Colorier les lignes NOK en rouge clair
        for i, c in enumerate(cycles_data, start=1):
            if c.get("result") != "PASS":
                detail_table.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, i),
                                (-1, i),
                                colors.HexColor("#ffebee"),
                            ),
                            (
                                "TEXTCOLOR",
                                (4, i),
                                (4, i),
                                colors.HexColor("#c62828"),
                            ),
                        ]
                    )
                )

        story.append(detail_table)
        doc.build(story)
        return True

    except Exception as e:
        print(f"[EXPORT] Erreur PDF: {e}")
        return False