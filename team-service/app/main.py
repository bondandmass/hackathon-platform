from .core.factory import build_app
from .routes import router

app = build_app("team-service", router)
