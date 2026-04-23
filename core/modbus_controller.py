# =====================================================
# TABLE D'ECHANGE MODBUS TCP — Delta DVP-AS228
# =====================================================
# Validé et testé le 2026-04-23
#
# D2000  (READ,  PLC → Pi)  ◀──▶  0x07D0 (2000 décimal)
#   bit 0 = DCY, bit 1 = TAR_Y, bit 2 = TAR_X
#
# D2001-D2002  (READ, PLC → Pi)  ◀──▶  0x07D1 (2001 décimal)
#   Float32 Little Endian (CDAB) — position en mm
#
# D2003-D2004  (READ, PLC → Pi)  ◀──▶  0x07D3 (2003 décimal)
#   Int32 signé Little Endian (CDAB) — force en DaN (non branché)
#
# D2100  (WRITE, Pi → PLC)  ◀──▶  0x0834 (2100 décimal)
#   bit 0 = PRET, bit 1 = OK, bit 2 = NOK,
#   bit 3 = NOPASS, bit 7 = ALARME
# =====================================================
"""Contrôleur Modbus TCP — communication avec automate Delta DVP.

Rôle :
  - Polling du registre D2000 (commandes PLC → Pi) toutes les 50 ms
  - D2000 bit 0 : départ cycle (DCY mesure)   → on_cycle_start / on_cycle_stop
  - D2000 bit 1 : tarage Y                    → on_tare_y
  - D2000 bit 2 : tarage X                    → on_tare_x
  - Écriture état Pi → PLC (D2100) :
      bit 0 : PRET   (1 dès init, 0 sur alarme critique)
      bit 1 : OK     (1 si dernier cycle conforme)
      bit 2 : NOK    (1 si dernier cycle non conforme)
      bit 3 : NOPASS (1 si zone NO-PASS traversée)
      bit 7 : ALARME (1 si erreur système ou capteur)

Architecture thread-safe :
  ModbusController tourne dans son propre thread daemon.
  Il communique avec le reste de l'application via callbacks Qt
  (passés depuis main.py, appelés thread-safe via AcquisitionBridge).
  Les registres de sortie sont maintenus en shadow local — écriture
  par masquage uniquement, jamais d'écrasement des autres bits.
"""

from __future__ import annotations

import struct
import threading
import time
from collections.abc import Callable
from pathlib import Path

import yaml

# Bits D2000 (entrées depuis PLC)
_BIT_DCY   = 0
_BIT_TAR_Y = 1
_BIT_TAR_X = 2

# Bits D2100 (sorties vers PLC)
_BIT_PRET   = 0
_BIT_OK     = 1
_BIT_NOK    = 2
_BIT_NOPASS = 3
_BIT_ALARME = 7


class ModbusController(threading.Thread):
    """Thread de polling Modbus TCP pour automate Delta DVP."""

    def __init__(
        self,
        config_path: Path,
        on_cycle_start: Callable[[], None] | None = None,
        on_cycle_stop: Callable[[], None] | None = None,
        on_tare_y: Callable[[], None] | None = None,
        on_tare_x: Callable[[], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Initialise le thread Modbus et ses callbacks applicatifs.

        Les callbacks sont optionnels et déclenchés sur fronts détectés
        dans D2000 (début/fin cycle, tarages Y/X).
        """
        super().__init__(name="ModbusController", daemon=True)
        self._stop_event = stop_event or threading.Event()
        self._on_cycle_start = on_cycle_start
        self._on_cycle_stop = on_cycle_stop
        self._on_tare_y = on_tare_y
        self._on_tare_x = on_tare_x
        self._status_callback: Callable[[bool], None] | None = None
        self._client = None
        self._connected = False

        self._last_cmd = 0          # dernier registre cmd lu (détection fronts)
        self._status_shadow = 0     # valeur locale D2100 (écriture par masque)
        self._shadow_lock = threading.Lock()

        self._config = self._load_config(config_path)
        self._cmd_read_addr      = int(str(self._config.get("cmd_read_addr",      "0x07D0")), 0)
        self._status_write_addr  = int(str(self._config.get("status_write_addr",  "0x0834")), 0)
        self._unit_id            = int(self._config.get("unit_id", 1))
        self._position_read_addr = int(str(self._config.get("position_read_addr", "0x07D1")), 0)
        self._force_read_addr    = int(str(self._config.get("force_read_addr",    "0x07D3")), 0)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(config_path: Path) -> dict:
        """Charge la section Modbus depuis le fichier YAML de configuration."""
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("modbus", {})
        except Exception as e:
            print(f"[MODBUS] Erreur lecture config: {e}")
            return {}

    # ------------------------------------------------------------------
    # Status callback
    # ------------------------------------------------------------------

    def set_status_callback(self, cb: Callable[[bool], None]) -> None:
        """Enregistre le callback de changement d'état de connexion."""
        self._status_callback = cb

    def _notify_status(self, connected: bool) -> None:
        """Notifie l'application quand l'état de connexion évolue."""
        if self._status_callback:
            self._status_callback(connected)

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------

    def _connect(self) -> bool:
        """Tente de se connecter à l'automate. Retourne True si succès."""
        try:
            from pymodbus.client import ModbusTcpClient

            host = self._config.get("host", "192.168.1.92")
            port = int(self._config.get("port", 502))
            self._client = ModbusTcpClient(host=host, port=port, timeout=2)
            result = self._client.connect()
            if result:
                print(f"[MODBUS] Connecté à {host}:{port}")
                self._connected = True
                self._notify_status(True)
                self._init_output_registers()
            else:
                print(f"[MODBUS] Échec connexion à {host}:{port}")
                self._connected = False
                self._notify_status(False)
            return self._connected
        except Exception as e:
            print(f"[MODBUS] Erreur connexion: {e}")
            self._connected = False
            self._notify_status(False)
            return False

    def _disconnect(self) -> None:
        """Ferme proprement le client Modbus et publie l'état déconnecté."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False
        self._client = None
        self._notify_status(False)

    # ------------------------------------------------------------------
    # Initialisation des registres de sortie
    # ------------------------------------------------------------------

    def _init_output_registers(self) -> None:
        """Après connexion : reset le shadow, puis active le bit Prêt."""
        with self._shadow_lock:
            self._status_shadow = 0
        self._write_status_bit(_BIT_PRET, True)
        print("[MODBUS] Registres initialisés — D2100 Prêt = 1")

    # ------------------------------------------------------------------
    # Primitives lecture / écriture (accès registre brut)
    # ------------------------------------------------------------------

    def _read_register(self, address: int) -> int | None:
        """Lit un registre Holding. Retourne la valeur ou None si erreur."""
        try:
            result = self._client.read_holding_registers(
                address=address, count=1, device_id=self._unit_id
            )
            if result.isError():
                return None
            return result.registers[0]
        except Exception:
            self._connected = False
            return None

    def _write_status_bit(self, bit: int, state: bool) -> None:
        """Modifie un bit de D2100 par masquage sur le shadow local."""
        with self._shadow_lock:
            if state:
                self._status_shadow |= (1 << bit)
            else:
                self._status_shadow &= ~(1 << bit)
            value = self._status_shadow
        try:
            self._client.write_register(
                address=self._status_write_addr, value=value, device_id=self._unit_id
            )
        except Exception as e:
            print(f"[MODBUS] Erreur écriture D2100: {e}")
            self._connected = False

    # ------------------------------------------------------------------
    # API publique — appelée depuis le thread Qt / main.py
    # ------------------------------------------------------------------

    def read_position(self) -> float | None:
        """Lit la position depuis l'automate (D2001-D2002).

        Retourne la valeur en mm, ou None si déconnecté ou erreur.
        Format : Float32 Little Endian (CDAB) — mot bas en r0, mot haut en r1.

        THREAD-SAFETY : doit être appelée UNIQUEMENT depuis le thread de
        polling Modbus (self.run()). Tout appel depuis un autre thread
        accéderait à self._client de façon concurrente sans verrou.
        """
        if not self._connected or self._client is None:
            return None
        try:
            rr = self._client.read_holding_registers(
                address=self._position_read_addr,
                count=2,
                device_id=self._unit_id,
            )
            if rr.isError():
                return None
            r0, r1 = rr.registers[0], rr.registers[1]
            raw = struct.pack(">HH", r1, r0)   # inversion des mots : CDAB → ABCD
            return struct.unpack(">f", raw)[0]
        except Exception as e:
            print(f"[MODBUS] Erreur lecture position: {e}")
            return None

    def read_force(self) -> int | None:
        """Lit la force depuis l'automate (D2003-D2004).

        Retourne la valeur en DaN (entier signé), ou None si déconnecté ou erreur.
        Format : Int32 signé Little Endian (CDAB) — mot bas en r0, mot haut en r1.

        THREAD-SAFETY : doit être appelée UNIQUEMENT depuis le thread de
        polling Modbus (self.run()). Tout appel depuis un autre thread
        accéderait à self._client de façon concurrente sans verrou.
        """
        if not self._connected or self._client is None:
            return None
        try:
            rr = self._client.read_holding_registers(
                address=self._force_read_addr,
                count=2,
                device_id=self._unit_id,
            )
            if rr.isError():
                return None
            r0, r1 = rr.registers[0], rr.registers[1]
            raw = struct.pack(">HH", r1, r0)   # inversion des mots : CDAB → ABCD
            return struct.unpack(">i", raw)[0]
        except Exception as e:
            print(f"[MODBUS] Erreur lecture force: {e}")
            return None

    def write_result(self, result: str, no_pass: bool = False) -> None:
        """Écrit le résultat du cycle dans D2100.

        OK et NOK sont mutuellement exclusifs : les deux sont remis à 0
        avant d'écrire le nouveau résultat.
        Appelé depuis on_cycle_finished dans main.py via signal Qt.
        """
        if not self._connected or not self._client:
            return
        is_pass = result == "PASS"
        with self._shadow_lock:
            # Effacer OK, NOK et NO-PASS avant de poser le résultat
            self._status_shadow &= ~(
                (1 << _BIT_OK) | (1 << _BIT_NOK) | (1 << _BIT_NOPASS)
            )
            if is_pass:
                self._status_shadow |= (1 << _BIT_OK)
            else:
                self._status_shadow |= (1 << _BIT_NOK)
                if no_pass:
                    self._status_shadow |= (1 << _BIT_NOPASS)
            value = self._status_shadow
        try:
            self._client.write_register(
                address=self._status_write_addr, value=value, device_id=self._unit_id
            )
            print(f"[MODBUS] Résultat D2100 = 0x{value:04X} ({result}"
                  f"{', NO-PASS' if no_pass else ''})")
        except Exception as e:
            print(f"[MODBUS] Erreur écriture résultat: {e}")
            self._connected = False

    def set_nopass(self, active: bool) -> None:
        """Active/désactive le bit NO-PASS dans D2100 (bit 3)."""
        if not self._connected or not self._client:
            return
        self._write_status_bit(_BIT_NOPASS, active)

    def set_alarm(self, alarm: bool) -> None:
        """Active/désactive l'alarme (D2100 bit 7).
        Une alarme critique efface aussi le bit Prêt."""
        if not self._connected or not self._client:
            return
        with self._shadow_lock:
            if alarm:
                self._status_shadow |= (1 << _BIT_ALARME)
                self._status_shadow &= ~(1 << _BIT_PRET)
            else:
                self._status_shadow &= ~(1 << _BIT_ALARME)
            value = self._status_shadow
        try:
            self._client.write_register(
                address=self._status_write_addr, value=value, device_id=self._unit_id
            )
            print(f"[MODBUS] Alarme {'ON' if alarm else 'OFF'} — D2100 = 0x{value:04X}")
        except Exception as e:
            print(f"[MODBUS] Erreur écriture alarme: {e}")
            self._connected = False

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Exécute la boucle de polling, gère reconnection et fronts D2000."""
        if not self._config.get("enabled", True):
            print("[MODBUS] Désactivé dans config.yaml")
            return

        poll_ms = int(self._config.get("poll_interval_ms", 50))

        while not self._stop_event.is_set() and not self._connected:
            if self._connect():
                break
            print("[MODBUS] Nouvelle tentative dans 5s...")
            for _ in range(50):
                if self._stop_event.is_set():
                    return
                time.sleep(0.1)

        print("[MODBUS] Polling démarré")

        while not self._stop_event.is_set():
            if not self._connected:
                self._disconnect()
                print("[MODBUS] Reconnexion dans 5s...")
                for _ in range(50):
                    if self._stop_event.is_set():
                        return
                    time.sleep(0.1)
                self._connect()
                continue

            # --- Lecture D2000 (commandes PLC → Pi) ---
            cmd_value = self._read_register(self._cmd_read_addr)

            if cmd_value is None:
                self._connected = False
                self._notify_status(False)
                continue

            prev = self._last_cmd

            # Front montant DCY → départ cycle
            dcy_now  = bool(cmd_value & (1 << _BIT_DCY))
            dcy_prev = bool(prev      & (1 << _BIT_DCY))
            if dcy_now and not dcy_prev:
                print("[MODBUS] DCY ↑ → démarrage cycle")
                if self._on_cycle_start:
                    self._on_cycle_start()

            # Front descendant DCY → fin cycle
            elif not dcy_now and dcy_prev:
                print("[MODBUS] DCY ↓ → fin cycle")
                if self._on_cycle_stop:
                    self._on_cycle_stop()

            # Front montant TAR_Y → tarage voie Y
            tar_y_now  = bool(cmd_value & (1 << _BIT_TAR_Y))
            tar_y_prev = bool(prev      & (1 << _BIT_TAR_Y))
            if tar_y_now and not tar_y_prev:
                print("[MODBUS] TAR_Y ↑ → tarage Y demandé")
                if self._on_tare_y:
                    self._on_tare_y()

            # Front montant TAR_X → tarage voie X
            tar_x_now  = bool(cmd_value & (1 << _BIT_TAR_X))
            tar_x_prev = bool(prev      & (1 << _BIT_TAR_X))
            if tar_x_now and not tar_x_prev:
                print("[MODBUS] TAR_X ↑ → tarage X demandé")
                if self._on_tare_x:
                    self._on_tare_x()

            self._last_cmd = cmd_value
            time.sleep(poll_ms / 1000.0)

        self._disconnect()
        print("[MODBUS] Thread arrêté")
