import json
from pathlib import Path

from app.domain.models import Network

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "network.json"


class JsonCatalog:
    """Red de transporte semilla (exportada de web/js/data.js)."""

    def __init__(self, path: Path = DEFAULT_PATH):
        self._path = path

    def load(self) -> Network:
        return Network.model_validate(json.loads(self._path.read_text(encoding="utf-8")))
