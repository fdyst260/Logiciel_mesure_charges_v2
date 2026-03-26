"""Module d'acquisition temps reel pour MCC 118 sur Raspberry Pi.

Ce module gere :
- L'acquisition bi-canal CH0 (Force) + CH1 (Position)
- Le declenchement via Modbus TCP (D200) ou trigger materiel optionnel
- La conversion Volts -> grandeurs physiques (N, mm)
- L'envoi des echantillons etalonnes vers une queue partagee
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config import (
    BOARD_NUM,
    CHUNK_SIZE,
    FORCE_CHANNEL,
    FORCE_NEWTON_MAX,
    FORCE_VOLT_MAX,
    POSITION_CHANNEL,
    POSITION_MM_MAX,
    POSITION_VOLT_MAX,
    READ_TIMEOUT_SEC,
    SAMPLE_RATE_HZ,
)

if TYPE_CHECKING:
    from daqhats import HatError as HatErrorType
else:
    HatErrorType = Exception

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
_ACQ_READ_TIMEOUT = 10.0  # secondes avant warning "aucune donnee depuis Xs"


def _read_trigger_mode() -> str:
    """Lit trigger_mode depuis config.yaml. Defaut: 'modbus'."""
    try:
        import yaml
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("acquisition", {}).get("trigger_mode", "modbus")
    except Exception:
        return "modbus"


class AcquisitionError(Exception):
    """Erreur applicative de la chaine d'acquisition."""


@dataclass(frozen=True)
class SensorCalibrator:
    """Etalonnage lineaire simple des capteurs.

    - force_n = voltage_force * force_gain
    - position_mm = voltage_pos * position_gain
    """

    force_gain: float = FORCE_NEWTON_MAX / FORCE_VOLT_MAX
    position_gain: float = POSITION_MM_MAX / POSITION_VOLT_MAX

    def calibrate_force(self, voltage: float) -> float:
        return voltage * self.force_gain

    def calibrate_position(self, voltage: float) -> float:
        return voltage * self.position_gain

    def calibrate_pair(self, voltage_force: float, voltage_position: float) -> tuple[float, float]:
        return (self.calibrate_force(voltage_force), self.calibrate_position(voltage_position))


def _load_daqhats() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    """Charge daqhats a l'execution.

    Ce chargement paresseux evite de bloquer l'import du module si daqhats
    n'est pas installe dans l'interpreteur utilise par l'IDE.
    """
    try:
        from daqhats import (
            HatError,
            HatIDs,
            OptionFlags,
            TriggerModes,
            hat_list,
            mcc118,
        )
    except ModuleNotFoundError as exc:
        raise AcquisitionError(
            "Module 'daqhats' introuvable. Installez la bibliotheque daqhats "
            "dans l'environnement Python qui execute l'acquisition."
        ) from exc

    return HatError, HatIDs, OptionFlags, TriggerModes, hat_list, mcc118


def _check_mcc118_available(board_num: int, hat_list_fn: Any, hat_ids: Any) -> None:
    """Verifie qu'une MCC 118 est presente a l'adresse demandee."""
    hats = hat_list_fn(filter_by_id=hat_ids.MCC_118)
    if not hats:
        raise AcquisitionError("Aucune carte MCC 118 detectee.")

    available_addresses = {hat.address for hat in hats}
    if board_num not in available_addresses:
        raise AcquisitionError(
            f"Carte MCC 118 non trouvee a l'adresse {board_num}. "
            f"Adresses disponibles: {sorted(available_addresses)}"
        )


def _channel_mask_for_force_position() -> int:
    """Construit le masque binaire pour CH0/CH1.

    Ex: CH0+CH1 -> 0b11 (decimal 3)
    """
    return (1 << FORCE_CHANNEL) | (1 << POSITION_CHANNEL)


def _wait_until_triggered(hat: Any, stop_event: threading.Event) -> None:
    """Attend le declenchement externe TRIG apres le scan start.

    Avec EXTTRIGGER, le scan est arme puis attend le front TRIG materiel.
    On surveille l'etat pour offrir une sortie propre si stop_event est active.
    """
    print("[ACQ] Scan arme. Attente du trigger externe TRIG...")
    while not stop_event.is_set():
        status = hat.a_in_scan_status()
        if getattr(status, "triggered", False):
            print("[ACQ] Trigger recu, acquisition en cours.")
            return
        time.sleep(0.002)



def acquisition_loop(
    data_queue: queue.Queue,
    stop_event: threading.Event,
    start_event: threading.Event | None = None,
    calibrator: SensorCalibrator | None = None,
) -> None:
    """Boucle producteur d'acquisition a la demande (trigger Modbus ou hardware).

    Le scan MCC 118 ne demarre PAS immediatement. Il attend que start_event
    soit set avant de lancer le scan. Cela evite de remplir la queue au
    demarrage de l'application.

    Parametres:
    - data_queue: queue partagee vers le thread d'analyse
    - stop_event: evenement d'arret global
    - start_event: evenement de demarrage du scan (si None, demarre immediatement)
    - calibrator: objet d'etalonnage (si None, calibrage par defaut)

    Donnees poussees dans la queue:
    - list[tuple[t, force_n, position_mm]]
      Chaque bloc correspond a CHUNK_SIZE points (si disponibles).
    """
    calibrator = calibrator or SensorCalibrator()

    HatError, HatIDs, OptionFlags, TriggerModes, hat_list_fn, mcc118_cls = _load_daqhats()
    _check_mcc118_available(BOARD_NUM, hat_list_fn=hat_list_fn, hat_ids=HatIDs)

    hat = mcc118_cls(BOARD_NUM)
    print("[ACQ] MCC 118 initialisee, scan PAS demarre (attente start_event).")

    # Attente du signal de demarrage
    if start_event is not None:
        while not stop_event.is_set():
            if start_event.wait(timeout=0.2):
                break
        if stop_event.is_set():
            print("[ACQ] Arret demande avant demarrage du scan.")
            return
        # Laisser le temps au DataProcessor de demarrer
        time.sleep(0.1)

    channel_mask = _channel_mask_for_force_position()

    # Lecture du mode trigger depuis config.yaml
    trigger_mode = _read_trigger_mode()
    if trigger_mode == "hardware":
        options = OptionFlags.CONTINUOUS | OptionFlags.EXTTRIGGER
        print("[ACQ] Mode trigger : HARDWARE (broche TRIG)")
    else:
        # Trigger gere par Modbus TCP (D200) — pas par trigger materiel
        options = OptionFlags.CONTINUOUS
        print("[ACQ] Mode trigger : MODBUS (D200)")

    try:
        if trigger_mode == "hardware":
            hat.trigger_mode(TriggerModes.RISING_EDGE)

        mode_str = "CONTINUOUS+EXTTRIGGER" if trigger_mode == "hardware" else "CONTINUOUS"
        print(
            f"[ACQ] Demarrage scan MCC118: CH{FORCE_CHANNEL}/CH{POSITION_CHANNEL}, "
            f"{SAMPLE_RATE_HZ:.0f} Hz/canal, chunk={CHUNK_SIZE}, mode {mode_str}"
        )
        hat.a_in_scan_start(
            channel_mask=channel_mask,
            samples_per_channel=CHUNK_SIZE,
            sample_rate_per_channel=SAMPLE_RATE_HZ,
            options=options,
        )

        if trigger_mode == "hardware":
            _wait_until_triggered(hat, stop_event)
            if stop_event.is_set():
                return

        last_data_time = time.perf_counter()

        while not stop_event.is_set():
            read_result = hat.a_in_scan_read(
                samples_per_channel=CHUNK_SIZE,
                timeout=READ_TIMEOUT_SEC,
            )

            if read_result.hardware_overrun:
                print("[ACQ] Warning: hardware overrun, chunk ignore")
                continue
            if read_result.buffer_overrun:
                print("[ACQ] Warning: buffer overrun, chunk ignore")
                continue

            raw = read_result.data
            if not raw:
                if time.perf_counter() - last_data_time > _ACQ_READ_TIMEOUT:
                    print("[ACQ] Warning: aucune donnee depuis 10s")
                    last_data_time = time.perf_counter()
                continue

            last_data_time = time.perf_counter()

            # Les donnees sont entrelacees: CH0, CH1, CH0, CH1...
            if len(raw) % 2 != 0:
                print("[ACQ] Warning: bloc incoherent (nombre impair), chunk ignore")
                continue

            t_start = time.perf_counter()
            calibrated_block: list[tuple[float, float, float]] = []
            for i in range(0, len(raw), 2):
                t = t_start + (i // 2) / SAMPLE_RATE_HZ
                v_force = float(raw[i])
                v_pos = float(raw[i + 1])
                force_n, pos_mm = calibrator.calibrate_pair(v_force, v_pos)
                calibrated_block.append((t, force_n, pos_mm))

            try:
                data_queue.put(calibrated_block, timeout=0.2)
            except queue.Full:
                print("[ACQ] Warning: queue pleine, chunk ignore")
                continue

    except HatError as exc:
        raise AcquisitionError(f"Erreur materielle MCC 118 (HatError): {exc}") from exc

    finally:
        # Arret propre meme en cas d'erreur/interruption.
        try:
            hat.a_in_scan_stop()
            hat.a_in_scan_cleanup()
        except Exception as e:
            print(f"[ACQ] Arret scan: {e}")

        print("[ACQ] Nettoyage acquisition termine.")
