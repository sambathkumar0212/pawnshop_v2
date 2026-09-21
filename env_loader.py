import os
from pathlib import Path

from dotenv import load_dotenv


def load_env():
    """Load the environment file for the selected Django environment if present."""
    base_dir = Path(__file__).resolve().parent
    env = os.getenv('DJANGO_ENV', 'development').strip().lower()
    candidates = [base_dir / f'.env.{env}', base_dir / '.env']

    for env_path in candidates:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"Loaded environment from {env_path.name}")
            return env_path

    # In cloud/production platforms (Render, Cloud Run, Heroku, Docker), environment
    # variables are injected directly via the platform rather than local .env files.
    return None
