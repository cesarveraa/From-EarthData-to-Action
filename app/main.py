from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .routers import data
from .core.config import settings
print("DEBUG OpenAQ API Key:", settings.openaq_api_key)
print("DEBUG Earthdata Username:", settings.earthdata_username)
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # ajusta para producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)

@app.get("/")
def root():
    return {"name": settings.app_name, "env": settings.app_env, "message": "OK"}
