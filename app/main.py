from fastapi import FastAPI
from .routers import validate_router, audit_router, reference_router

app = FastAPI(title="MCP FE Compliance Service")
app.include_router(validate_router)
app.include_router(audit_router)
app.include_router(reference_router)


@app.get("/")
def root():
    return {"status": "ok"}
