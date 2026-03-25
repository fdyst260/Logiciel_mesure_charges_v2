"""Système de traduction pour l'IHM ACM Riveteuse.

Utilisation :
    from ihm.translations import t, set_language
    set_language("en")
    print(t("status_running"))  # → RUNNING
"""

from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "fr": "Français",
    "en": "English",
    "it": "Italiano",
    "es": "Español",
    "pt": "Português",
    "ro": "Română",
}

TRANSLATIONS: dict[str, dict[str, str]] = {

    # --- Écran principal ---
    "status_idle":     {"fr": "ATTENTE",    "en": "WAITING",
                        "it": "ATTESA",     "es": "ESPERA",
                        "pt": "AGUARDAR",   "ro": "AȘTEPTARE"},
    "status_running":  {"fr": "EN COURS",   "en": "RUNNING",
                        "it": "IN CORSO",   "es": "EN CURSO",
                        "pt": "EM CURSO",   "ro": "ÎN CURS"},
    "status_ok":       {"fr": "OK",         "en": "OK",
                        "it": "OK",         "es": "OK",
                        "pt": "OK",         "ro": "OK"},
    "status_nok":      {"fr": "NOK",        "en": "NOK",
                        "it": "NOK",        "es": "NOK",
                        "pt": "NOK",        "ro": "NOK"},

    # --- Panneau droit ---
    "fmax_label":      {"fr": "Fmax",       "en": "Fmax",
                        "it": "Fmax",       "es": "Fmax",
                        "pt": "Fmax",       "ro": "Fmax"},
    "xmax_label":      {"fr": "Xmax",       "en": "Xmax",
                        "it": "Xmax",       "es": "Xmax",
                        "pt": "Xmax",       "ro": "Xmax"},
    "force_label":     {"fr": "Force",      "en": "Force",
                        "it": "Forza",      "es": "Fuerza",
                        "pt": "Força",      "ro": "Forță"},
    "position_label":  {"fr": "Position",   "en": "Position",
                        "it": "Posizione",  "es": "Posición",
                        "pt": "Posição",    "ro": "Poziție"},
    "modbus_connected":    {"fr": "Modbus : Connecté",
                            "en": "Modbus: Connected",
                            "it": "Modbus: Connesso",
                            "es": "Modbus: Conectado",
                            "pt": "Modbus: Conectado",
                            "ro": "Modbus: Conectat"},
    "modbus_disconnected": {"fr": "Modbus : Déconnecté",
                            "en": "Modbus: Disconnected",
                            "it": "Modbus: Disconnesso",
                            "es": "Modbus: Desconectado",
                            "pt": "Modbus: Desconectado",
                            "ro": "Modbus: Deconectat"},
    "btn_settings":    {"fr": "RÉGLAGES",   "en": "SETTINGS",
                        "it": "IMPOSTAZIONI","es": "AJUSTES",
                        "pt": "DEFINIÇÕES", "ro": "SETĂRI"},
    "btn_new_cycle":   {"fr": "NOUVEAU CYCLE","en": "NEW CYCLE",
                        "it": "NUOVO CICLO","es": "NUEVO CICLO",
                        "pt": "NOVO CICLO", "ro": "CICLU NOU"},

    # --- Barre de navigation ---
    "nav_current":     {"fr": "Courbe actuelle","en": "Current curve",
                        "it": "Curva attuale","es": "Curva actual",
                        "pt": "Curva atual", "ro": "Curba curentă"},
    "nav_history":     {"fr": "Historique", "en": "History",
                        "it": "Storico",    "es": "Historial",
                        "pt": "Histórico",  "ro": "Istoric"},
    "nav_data":        {"fr": "Données",    "en": "Data",
                        "it": "Dati",       "es": "Datos",
                        "pt": "Dados",      "ro": "Date"},
    "nav_stats":       {"fr": "Statistiques","en": "Statistics",
                        "it": "Statistiche","es": "Estadísticas",
                        "pt": "Estatísticas","ro": "Statistici"},
    "nav_raz":         {"fr": "RAZ",        "en": "RESET",
                        "it": "RAZ",        "es": "RAZ",
                        "pt": "RAZ",        "ro": "RAZ"},

    # --- Niveaux d'accès ---
    "level_free":      {"fr": "Libre",      "en": "Free",
                        "it": "Libero",     "es": "Libre",
                        "pt": "Livre",      "ro": "Liber"},
    "level_locked":    {"fr": "Verrouillé", "en": "Locked",
                        "it": "Bloccato",   "es": "Bloqueado",
                        "pt": "Bloqueado",  "ro": "Blocat"},
    "level_operator":  {"fr": "Opérateur",  "en": "Operator",
                        "it": "Operatore",  "es": "Operador",
                        "pt": "Operador",   "ro": "Operator"},
    "level_tech":      {"fr": "Technicien", "en": "Technician",
                        "it": "Tecnico",    "es": "Técnico",
                        "pt": "Técnico",    "ro": "Tehnician"},
    "level_admin":     {"fr": "Administrateur","en": "Administrator",
                        "it": "Amministratore","es": "Administrador",
                        "pt": "Administrador","ro": "Administrator"},
    "btn_login":       {"fr": "Se connecter","en": "Log in",
                        "it": "Accedi",     "es": "Iniciar sesión",
                        "pt": "Entrar",     "ro": "Conectare"},
    "btn_logout":      {"fr": "Déconnexion","en": "Log out",
                        "it": "Disconnetti","es": "Cerrar sesión",
                        "pt": "Sair",       "ro": "Deconectare"},

    # --- Réglages ---
    "settings_title":  {"fr": "Réglages",   "en": "Settings",
                        "it": "Impostazioni","es": "Ajustes",
                        "pt": "Definições", "ro": "Setări"},
    "btn_back":        {"fr": "Retour",     "en": "Back",
                        "it": "Indietro",   "es": "Volver",
                        "pt": "Voltar",     "ro": "Înapoi"},
    "btn_save":        {"fr": "Sauvegarder","en": "Save",
                        "it": "Salva",      "es": "Guardar",
                        "pt": "Guardar",    "ro": "Salvare"},
    "btn_cancel":      {"fr": "Annuler",    "en": "Cancel",
                        "it": "Annulla",    "es": "Cancelar",
                        "pt": "Cancelar",   "ro": "Anulare"},
}


def get(key: str, lang: str = "fr") -> str:
    """Retourne la traduction d'une clé pour la langue donnée.

    Fallback : français si la langue n'existe pas,
    puis la clé brute si la traduction manque.
    """
    entry = TRANSLATIONS.get(key, {})
    return entry.get(lang) or entry.get("fr") or key


# Langue courante (module-level state)
_current_lang: str = "fr"


def set_language(lang: str) -> None:
    """Change la langue courante."""
    global _current_lang
    if lang in LANGUAGES:
        _current_lang = lang


def get_language() -> str:
    """Retourne le code de la langue courante."""
    return _current_lang


def t(key: str) -> str:
    """Raccourci : traduit avec la langue courante."""
    return get(key, _current_lang)