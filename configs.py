# configs.py
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
    DEFAULT_MODEL = "openai/gpt-oss-20b"
    #TF_REPORTS_PATH = Path("trendforce_reports/may_rpt.json")
    
    @classmethod
    def validate(cls):
        """Ensure all keys are present at startup."""
        missing = [k for k, v in cls.__dict__.items() if not k.startswith("__") and v is None]
        if missing:
            raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")
