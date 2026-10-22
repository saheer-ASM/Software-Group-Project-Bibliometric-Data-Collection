"""Load local configuration without connecting to any external service."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Union

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / "config" / "config.env"
CONFIG_KEYS = (
    "DB_ENGINE", "DB_PATH",
    "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSLMODE",
)


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration only; sensitive connection details are excluded from repr."""

    host: str = field(repr=False)
    port: int
    name: str = field(repr=False)
    user: str = field(repr=False)
    password: str = field(repr=False)
    sslmode: str

    def __post_init__(self):
        if not all(isinstance(value, str) and value for value in (self.host, self.name, self.user, self.password)):
            raise ValueError("Explicit database configuration must contain host, name, user and password.")
        if not isinstance(self.port, int) or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise ValueError("DB_PORT must be an integer between 1 and 65535.")
        if self.sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("DB_SSLMODE must be require, verify-ca, or verify-full.")


@dataclass(frozen=True)
class SQLiteConfig:
    """Local SQLite database file, always opened read-only; the path is excluded from repr."""

    path: Path = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.path, Path) or not self.path.is_file():
            raise ValueError("DB_PATH must name an existing SQLite database file.")


def load_config(env_file: Optional[Union[str, Path]] = None) -> Union[DatabaseConfig, SQLiteConfig]:
    """Read only this project's env file, with no ambient credential discovery.

    Relative paths resolve against PROJECT_ROOT. Parent-directory env discovery
    and dotenv interpolation are deliberately disabled. No connection is opened.
    """
    path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if PROJECT_ROOT not in path.parents:
        raise ValueError("The environment file must be inside the validation project.")
    if env_file is not None and not path.is_file():
        raise FileNotFoundError("The specified environment file does not exist.")

    values = dotenv_values(path, interpolate=False) if path.is_file() else {}
    values = {key: values.get(key) for key in CONFIG_KEYS}
    engine = (values.get("DB_ENGINE") or "postgresql").strip().lower()
    if engine == "sqlite":
        if not values.get("DB_PATH"):
            raise ValueError("Missing configuration keys: DB_PATH")
        # Relative paths resolve against PROJECT_ROOT; the file itself may live outside it.
        db_path = Path(values["DB_PATH"])
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        return SQLiteConfig(path=db_path.resolve())
    if engine != "postgresql":
        raise ValueError("DB_ENGINE must be postgresql or sqlite.")
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError("Missing configuration keys: " + ", ".join(missing))

    try:
        port = int(values.get("DB_PORT") or "5432")
    except ValueError:
        raise ValueError("DB_PORT must be an integer between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be an integer between 1 and 65535.")

    sslmode = values.get("DB_SSLMODE") or "require"
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("DB_SSLMODE must be require, verify-ca, or verify-full.")

    return DatabaseConfig(
        host=values["DB_HOST"], port=port, name=values["DB_NAME"],
        user=values["DB_USER"], password=values["DB_PASSWORD"], sslmode=sslmode,
    )


@dataclass(frozen=True)
class ValidationConfig:
    as_of_date: Optional[date]
    min_publications: int
    min_metric_coverage: float
    random_seed: int
    output_directory: Path
    min_raw_cites: int = 10


def load_validation_config(env_file: Optional[Union[str, Path]] = None) -> ValidationConfig:
    """Load non-secret run settings without requiring or opening a DB connection."""
    path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if PROJECT_ROOT not in path.parents:
        raise ValueError('The environment file must be inside the validation project.')
    values = dotenv_values(path, interpolate=False) if path.is_file() else {}
    as_of = date.fromisoformat(values['VALIDATION_AS_OF_DATE']) if values.get('VALIDATION_AS_OF_DATE') else None
    minimum = int(values.get('MIN_PUBLICATIONS') or 5)
    min_cites = int(values.get('MIN_RAW_CITES') or 10)
    coverage = float(values.get('MIN_METRIC_COVERAGE') or 0)
    seed = int(values.get('RANDOM_SEED') or 2026)
    output = (PROJECT_ROOT / (values.get('OUTPUT_DIRECTORY') or 'results')).resolve()
    results_root = (PROJECT_ROOT/'results').resolve()
    if minimum < 0 or min_cites < 0 or not 0 <= coverage <= 1 or (output != results_root and results_root not in output.parents):
        raise ValueError('Validation settings must be nonnegative, coverage within [0,1], and output inside results/.')
    return ValidationConfig(as_of, minimum, coverage, seed, output, min_cites)
