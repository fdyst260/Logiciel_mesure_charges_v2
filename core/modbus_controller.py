"""Contrôleur Modbus TCP — communication avec automate Delta DVP.

Rôle :
  - Polling du registre D200 (trigger) toutes les 50 ms
  - Détection front montant (0→1) → démarre un cycle
  - Détection front descendant (1→0) → termine le cycle
  - Écriture du résultat dans D201 après chaque cycle (1=PASS, 2=NOK)

Architecture thread-safe :
  ModbusController tourne dans son propre thread daemon.
  Il communique avec le reste de l'application via callbacks Qt
  (passés depuis main.py, appelés thread-safe via AcquisitionBridge).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import yaml


class ModbusController(threading.Thread):
    """Thread de polling Modbus TCP pour automate Delta DVP."""

    def __init__(
        self,
        config_path: Path,
        on_cycle_start: Callable[[], None] | None = None,
        on_cycle_stop: Callable[[], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        super().__init__(name="ModbusController", daemon=True)
        self._stop_event = stop_event or threading.Event()
        self._on_cycle_start = on_cycle_start
        self._on_cycle_stop = on_cycle_stop
        self._status_callback: Callable[[bool], None] | None = None
        self._client = None
        self._connected = False
        self._last_trigger = 0
        self._config = self._load_config(config_path)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(config_path: Path) -> dict:
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
        self._status_callback = cb

    def _notify_status(self, connected: bool) -> None:
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
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False
        self._client = None
        self._notify_status(False)

    # ------------------------------------------------------------------
    # Lecture / Écriture registres
    # ------------------------------------------------------------------

    def _read_register(self, address: int) -> int | None:
        """Lit un registre Holding. Retourne la valeur ou None si erreur."""
        try:
            result = self._client.read_holding_registers(address=address, count=1)
            if result.isError():
                return None
            return result.registers[0]
        except Exception:
            self._connected = False
            return None

    def write_result(self, result: str) -> None:
        """Écrit le résultat du cycle dans D201 (1=PASS, 2=NOK).
        Appelé depuis on_cycle_finished dans main.py."""
        if not self._connected or not self._client:
            return
        value = 1 if result == "PASS" else 2
        address = int(self._config.get("result_register", 0x10C9))
        try:
            self._client.write_register(address=address, value=value)
            print(f"[MODBUS] Résultat écrit D201 = {value} ({result})")
        except Exception as e:
            print(f"[MODBUS] Erreur écriture résultat: {e}")

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    def run(self) -> None:
        if not self._config.get("enabled", True):
            print("[MODBUS] Désactivé dans config.yaml")
            return

        poll_ms = int(self._config.get("poll_interval_ms", 50))
        trigger_addr = int(self._config.get("trigger_register", 0x10C8))

        # Tentatives de connexion avec retry
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

            # Lecture trigger D200
            value = self._read_register(trigger_addr)

            if value is None:
                # Perte de connexion
                self._connected = False
                self._notify_status(False)
                continue

            # Détection front montant 0→1
            if value == 1 and self._last_trigger == 0:
                print("[MODBUS] Front montant détecté → démarrage cycle")
                if self._on_cycle_start:
                    self._on_cycle_start()

            # Détection front descendant 1→0
            elif value == 0 and self._last_trigger == 1:
                print("[MODBUS] Front descendant détecté → fin cycle")
                if self._on_cycle_stop:
                    self._on_cycle_stop()

            self._last_trigger = value
            time.sleep(poll_ms / 1000.0)

        self._disconnect()
        print("[MODBUS] Thread arrêté")