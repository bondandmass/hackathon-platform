from .core.factory import build_app
from .routes import router
from .storage import bucket

bucket()  # fail fast if S3_BUCKET is missing
app = build_app("submission-service", router)
