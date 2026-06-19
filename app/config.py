from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "best_reserve_model.pkl"
PREPROCESS_CONFIG_PATH = BASE_DIR / "models" / "preprocess_config.json"
