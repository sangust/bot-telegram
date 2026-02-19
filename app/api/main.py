from fastapi import FastAPI
from .routes.landingpage import landingpage as front_router

app = FastAPI()
app.include_router(front_router)

