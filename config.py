"""Configuration centralisee du projet d'acquisition bi-canal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Carte MCC 118
BOARD_NUM = 0

# Acquisition bi-canal
FORCE_CHANNEL = 0       # CH0: Force 0-10V
POSITION_CHANNEL = 1    # CH1: Position 0-10V
CHANNELS = (FORCE_CHANNEL, POSITION_CHANNEL)

# Frequence d'echantillonnage par canal
SAMPLE_RATE_HZ = 5000.0

# Taille de bloc de lecture (50 ms a 5 kHz)
CHUNK_SIZE = 250
READ_TIMEOUT_SEC = 0.2
QUEUE_MAXSIZE = 200

# Timeouts arrêt des threads (secondes)
THREAD_JOIN_TIMEOUT  = 4.0   # DataProcessor
ACQ_THREAD_TIMEOUT   = 2.0   # AcquisitionThread
MODBUS_THREAD_TIMEOUT = 3.0  # ModbusController

# Trigger externe (signal GO sur GPIO de la Pi)
GO_TRIGGER_GPIO = 17
GO_TRIGGER_ACTIVE_HIGH = True
GO_POLL_INTERVAL_SEC = 0.001

# Echelles de conversion
FORCE_VOLT_MAX = 10.0
FORCE_NEWTON_MAX = 15000.0
POSITION_VOLT_MAX = 10.0
POSITION_MM_MAX = 20.0

# Seuils d'alarme (temps reel)
FORCE_THRESHOLD_N = 13000.0
POSITION_THRESHOLD_MM = 18.0

# Dossier d'export CSV
DATA_DIR = "./data"

# Nombre maximum de zones NO-PASS et UNI-BOX par PM
MAX_NO_PASS_ZONES = 5
MAX_UNI_BOX_ZONES = 5

# Sorties GPIO (Pi 5)
GPIO_OUT_OK = 5
GPIO_OUT_NOK = 6
GPIO_OUT_ALARM = 13


@dataclass(frozen=True)
class ProgramMeasure:
    """Definition d'un Programme de Mesure (PM)."""

    pm_id: int
    name: str
    description: str
    view_mode: str


PM_DEFINITIONS: dict[int, ProgramMeasure] = {
    1: ProgramMeasure(1, "PM01_STANDARD", "Rivetage standard", "FORCE_POSITION"),
    2: ProgramMeasure(2, "PM02_SOUPLE", "Assemblage souple", "FORCE_POSITION"),
    3: ProgramMeasure(3, "PM03_RIGIDE", "Assemblage rigide", "FORCE_POSITION"),
    4: ProgramMeasure(4, "PM04_COURT", "Cycle court", "FORCE_TIME"),
    5: ProgramMeasure(5, "PM05_LONG", "Cycle long", "FORCE_TIME"),
    6: ProgramMeasure(6, "PM06_PRECIS", "Positionnement precis", "POSITION_TIME"),
    7: ProgramMeasure(7, "PM07_HAUTE_FORCE", "Force elevee", "FORCE_POSITION"),
    8: ProgramMeasure(8, "PM08_FAIBLE_FORCE", "Force reduite", "FORCE_POSITION"),
    9: ProgramMeasure(9, "PM09_VALIDATION", "Validation process", "FORCE_POSITION"),
    10: ProgramMeasure(10, "PM10_PROTO", "Prototype", "FORCE_POSITION"),
    11: ProgramMeasure(11, "PM11_TEST_A", "Test qualification A", "FORCE_TIME"),
    12: ProgramMeasure(12, "PM12_TEST_B", "Test qualification B", "POSITION_TIME"),
    13: ProgramMeasure(13, "PM13_SERIE_A", "Production serie A", "FORCE_POSITION"),
    14: ProgramMeasure(14, "PM14_SERIE_B", "Production serie B", "FORCE_POSITION"),
    15: ProgramMeasure(15, "PM15_MAINT", "Maintenance / diagnostic", "FORCE_TIME"),
    16: ProgramMeasure(16, "PM16_CUSTOM", "Recette personnalisee", "FORCE_POSITION"),
    **{
        pm_id: ProgramMeasure(pm_id, f"PM{pm_id:02d}", "", "FORCE_POSITION")
        for pm_id in range(17, 51)
    },
}


def load_scaling_config() -> None:
    """Charge les valeurs de scaling et acquisition depuis config.yaml."""
    import yaml
    global FORCE_NEWTON_MAX, POSITION_MM_MAX, FORCE_THRESHOLD_N, POSITION_THRESHOLD_MM
    global SAMPLE_RATE_HZ, CHUNK_SIZE

    cfg_path = Path(__file__).parent / "config.yaml"
    if not cfg_path.exists():
        return
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return

    # Charger scaling
    scaling = cfg.get("scaling", {})
    if scaling.get("force_newton_max"):
        FORCE_NEWTON_MAX = float(scaling["force_newton_max"])
    if scaling.get("position_mm_max"):
        POSITION_MM_MAX = float(scaling["position_mm_max"])

    # Charger thresholds
    thresholds = cfg.get("thresholds", {})
    if thresholds.get("force_max_n"):
        FORCE_THRESHOLD_N = float(thresholds["force_max_n"])
    if thresholds.get("position_max_mm"):
        POSITION_THRESHOLD_MM = float(thresholds["position_max_mm"])

    # Charger acquisition parameters
    acq = cfg.get("acquisition", {})
    if acq.get("sample_rate_hz"):
        SAMPLE_RATE_HZ = float(acq["sample_rate_hz"])
    if acq.get("chunk_size"):
        CHUNK_SIZE = int(acq["chunk_size"])


def load_pm_from_yaml() -> None:
    """Charge les PM depuis config.yaml si la section 'programmes' existe."""
    import yaml

    cfg_path = Path(__file__).parent / "config.yaml"
    if not cfg_path.exists():
        return
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return
    for pm_id, pm_data in cfg.get("programmes", {}).items():
        if not isinstance(pm_id, int) or pm_id < 1 or pm_id > 50:
            continue
        default_name = PM_DEFINITIONS[pm_id].name if pm_id in PM_DEFINITIONS else f"PM{pm_id:02d}"
        PM_DEFINITIONS[pm_id] = ProgramMeasure(
            pm_id=pm_id,
            name=pm_data.get("name", default_name),
            description=pm_data.get("description", ""),
            view_mode=pm_data.get("view_mode", "FORCE_POSITION"),
        )


def build_default_tools() -> list:
    """Jeu d'outils d'évaluation par défaut pour Force=f(Position)."""
    from core.models import EvaluationTool, EvaluationType, Point2D

    return [
        EvaluationTool(
            name="no_pass_overload",
            tool_type=EvaluationType.NO_PASS,
            x_min=20.0,
            x_max=80.0,
            y_limit=4200.0,
        ),
        EvaluationTool(
            name="uni_box_fitting",
            tool_type=EvaluationType.UNI_BOX,
            box_x_min=10.0,
            box_x_max=40.0,
            box_y_min=500.0,
            box_y_max=2500.0,
            entry_side="left",
            exit_side="right",
        ),
        EvaluationTool(
            name="envelope_signature",
            tool_type=EvaluationType.ENVELOPE,
            lower_curve=[Point2D(0.0, 0.0), Point2D(100.0, 3000.0)],
            upper_curve=[Point2D(0.0, 500.0), Point2D(100.0, 5000.0)],
        ),
    ]


def build_tools_from_yaml(pm_id: int) -> list:
    """Charge les outils d'évaluation depuis config.yaml pour un PM donné."""
    import yaml
    from core.models import EvaluationTool, EvaluationType, Point2D

    cfg_path = Path(__file__).parent / "config.yaml"
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        tools_data = cfg.get("programmes", {}).get(pm_id, {}).get("tools", {})
    except Exception:
        return build_default_tools()

    tools: list = []

    # NO-PASS multi-zones
    np_zones = tools_data.get("no_pass_zones", [])

    # Compatibilité ancien format (no_pass unique → zone 1)
    if not np_zones:
        old = tools_data.get("no_pass", {})
        if old.get("enabled"):
            np_zones = [{
                "enabled": True,
                "x_min":   float(old.get("x_min", 0.0)),
                "x_max":   float(old.get("x_max", 0.0)),
                "y_limit": float(old.get("y_limit", 0.0)),
            }]

    for i, zone in enumerate(np_zones[:MAX_NO_PASS_ZONES]):
        if zone.get("enabled", False):
            tools.append(EvaluationTool(
                name=f"no_pass_{i + 1}",
                tool_type=EvaluationType.NO_PASS,
                zone_name=f"Zone {i + 1}",
                x_min=float(zone["x_min"]),
                x_max=float(zone["x_max"]),
                y_limit=float(zone["y_limit"]),
            ))

    # UNI-BOX multi-zones
    ub_zones = tools_data.get("uni_box_zones", [])
    # Compatibilité ancien format (uni_box unique → zone 1)
    if not ub_zones and tools_data.get("uni_box", {}):
        old_ub = tools_data["uni_box"]
        if old_ub.get("enabled"):
            ub_zones = [{
                "enabled":   True,
                "box_x_min": float(old_ub.get("box_x_min", 0.0)),
                "box_x_max": float(old_ub.get("box_x_max", 0.0)),
                "box_y_min": float(old_ub.get("box_y_min", 0.0)),
                "box_y_max": float(old_ub.get("box_y_max", 0.0)),
                "entry_side": old_ub.get("entry_side", "left"),
                "exit_side":  old_ub.get("exit_side", "left"),
            }]

    for i, zone in enumerate(ub_zones[:MAX_UNI_BOX_ZONES]):
        if zone.get("enabled", False):
            tools.append(EvaluationTool(
                name=f"uni_box_{i + 1}",
                tool_type=EvaluationType.UNI_BOX,
                zone_name=f"Zone {i + 1}",
                box_x_min=float(zone["box_x_min"]),
                box_x_max=float(zone["box_x_max"]),
                box_y_min=float(zone["box_y_min"]),
                box_y_max=float(zone["box_y_max"]),
                entry_side=zone.get("entry_side", "left"),
                exit_side=zone.get("exit_side", "left"),
            ))

    env_d = tools_data.get("envelope", {})
    if env_d.get("enabled", False):
        tools.append(EvaluationTool(
            name="envelope",
            tool_type=EvaluationType.ENVELOPE,
            lower_curve=[Point2D(p[0], p[1]) for p in env_d["lower_curve"]],
            upper_curve=[Point2D(p[0], p[1]) for p in env_d["upper_curve"]],
        ))

    return tools if tools else build_default_tools()


def volts_to_force(voltage: float) -> float:
    """Convertit une tension CH0 (0-10V) en Newton."""
    return (voltage / FORCE_VOLT_MAX) * FORCE_NEWTON_MAX


def volts_to_position(voltage: float) -> float:
    """Convertit une tension CH1 (0-10V) en mm."""
    return (voltage / POSITION_VOLT_MAX) * POSITION_MM_MAX


# Chargement automatique depuis config.yaml à l'import
load_scaling_config()
