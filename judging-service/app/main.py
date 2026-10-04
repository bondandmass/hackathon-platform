from .core.factory import build_app
from .routes import router

app = build_app("judging-service", router)
