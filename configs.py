# configs.py - Render-safe version
import os

class Config:
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
    DEFAULT_MODEL = "openai/gpt-oss-20b"
    
    @classmethod
    def validate(cls):
        missing = [k for k, v in cls.__dict__.items() 
                  if not k.startswith("__") and k.isupper() and v is None]
        if missing:
            raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")