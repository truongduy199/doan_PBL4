"""FastAPI Local Interface."""
from fastapi import FastAPI
from smart_parking.interfaces.http.routes import health, reviews

app = FastAPI(title="Smart Parking Edge Local API")
app.include_router(health.router)
app.include_router(reviews.router)