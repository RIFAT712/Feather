from fastapi import FastAPI, HTTPException
from shared_lib.schemas import ValidationRequestPayload, ValidationResult
from shared_lib.logger import setup_logger
from .parser import validate_articles, close_parser_client
import uvicorn
import os

logger = setup_logger("validator-service")

app = FastAPI(title="Wiktionary Validator Service")

@app.post("/validate", response_model=list[ValidationResult])
async def validate(payload: ValidationRequestPayload):
    try:
        logger.info(f"Received validation request for {len(payload.titles)} articles in contest {payload.contest_code}")
        results = await validate_articles(payload)
        return results
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    # Return 200 OK if the service is up
    return {"status": "ok", "service": "validator"}

@app.on_event("shutdown")
async def shutdown():
    await close_parser_client()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
