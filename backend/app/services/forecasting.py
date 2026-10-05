from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def personal_forecast(records: list[dict]) -> dict | None:
    try:
        from ml.predict import forecast
        return forecast(records)
    except ImportError:
        # Core tracking keeps working when optional ML packages are not installed.
        return None
