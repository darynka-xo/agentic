from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel, Field

from agents import build_crew
from config import get_db
from core.calculator import run_deterministic_calculator
from pdf_processor import process_pdf_to_rows
from minio_storage import (
    get_minio_storage_service,
    is_minio_configured,
    MinioServiceException
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


app = FastAPI(title="LLM-Smeta-PIR API")
crew_cache = None


class MinioPathRequest(BaseModel):
    """Request model for MinIO file path."""
    file_path: str = Field(..., description="Path to PDF file in MinIO bucket")
    bucket_name: Optional[str] = Field(None, description="Optional bucket name override")


def _init_crew():
    db = get_db()
    return build_crew(db)


@app.on_event("startup")
def on_startup():
    global crew_cache
    logger.info("Starting up server and initializing crew")
    try:
        crew_cache = _init_crew()
        logger.info("Crew initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize crew: {str(e)}", exc_info=True)
        raise


def _extract_payload(request: Dict[str, Any]) -> Dict[str, Any]:
    if "tabula_json" in request:
        tabula_json = request["tabula_json"]
    else:
        tabula_json = request

    if not isinstance(tabula_json, dict):
        raise HTTPException(
            status_code=400, detail="tabula_json payload must be a JSON object."
        )
    return tabula_json


@app.post("/predict")
def predict(tabula_request: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    logger.info("Received /predict request")
    
    if crew_cache is None:
        logger.error("Crew cache is None - initialization failed")
        raise HTTPException(status_code=503, detail="Crew initialization pending.")

    tabula_json = _extract_payload(tabula_request)
    logger.info(f"Extracted tabula_json payload with keys: {list(tabula_json.keys())}")
    
    try:
        logger.info("Starting crew run")
        state = crew_cache.run(tabula_json)
        logger.info("Crew run completed successfully")
        
        logger.info("Running deterministic calculator")
        state = run_deterministic_calculator(state)
        logger.info("Calculation completed successfully")
        
        return {"output": state.model_dump()}
    except ValueError as exc:
        logger.error(f"ValueError in predict: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logger.error(f"Unexpected error in predict: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/predict_pdf")
async def predict_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Новый endpoint для загрузки PDF файла.
    Автоматически извлекает таблицы и проверяет каждую строку.
    """
    logger.info(f"Received PDF upload: {file.filename}")
    
    if crew_cache is None:
        raise HTTPException(status_code=503, detail="Crew initialization pending.")
    
    # Проверяем что это PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Читаем содержимое файла
        pdf_content = await file.read()
        logger.info(f"Read {len(pdf_content)} bytes from PDF")
        
        # Извлекаем таблицы из PDF
        logger.info("Extracting tables from PDF using tabula...")
        tables = process_pdf_to_rows(pdf_content, file.filename)
        logger.info(f"Extracted {len(tables)} tables from PDF")
        
        # Обрабатываем каждую таблицу
        results = []
        for i, table_data in enumerate(tables, 1):
            logger.info(f"Processing table {i}/{len(tables)}")
            
            try:
                # Запускаем проверку
                state = crew_cache.run(table_data)
                state = run_deterministic_calculator(state)
                
                results.append({
                    "table_index": i,
                    "status": "success",
                    "output": state.model_dump()
                })
                
            except Exception as e:
                logger.error(f"Error processing table {i}: {str(e)}")
                results.append({
                    "table_index": i,
                    "status": "error",
                    "error": str(e)
                })
        
        # Возвращаем результаты всех таблиц
        return {
            "filename": file.filename,
            "tables_processed": len(tables),
            "results": results
        }
        
    except Exception as exc:
        logger.error(f"Error processing PDF: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(exc)}") from exc


@app.post("/predict_pdf_minio")
async def predict_pdf_minio(request: MinioPathRequest) -> Dict[str, Any]:
    """
    Endpoint для обработки PDF файла из MinIO по пути.
    Загружает файл из MinIO, извлекает таблицы и проверяет каждую строку.
    
    Args:
        request: MinioPathRequest с путем к файлу в MinIO
        
    Returns:
        Dict с результатами обработки всех таблиц
    """
    logger.info(f"Received MinIO PDF path request: {request.file_path}")
    
    if crew_cache is None:
        raise HTTPException(status_code=503, detail="Crew initialization pending.")
    
    # Проверяем что MinIO настроен
    if not is_minio_configured():
        raise HTTPException(
            status_code=503,
            detail="MinIO is not configured. Please set MINIO_ENDPOINT and MINIO_BUCKET_NAME."
        )
    
    # Проверяем что это PDF
    if not request.file_path.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Path must end with .pdf"
        )
    
    try:
        # Получаем MinIO сервис
        minio_service = get_minio_storage_service()
        
        # Проверяем существование файла
        if not minio_service.file_exists(request.file_path, request.bucket_name):
            logger.error(f"File not found in MinIO: {request.file_path}")
            raise HTTPException(
                status_code=404,
                detail=f"File not found in MinIO: {request.file_path}"
            )
        
        # Загружаем файл из MinIO
        logger.info(f"Downloading PDF from MinIO: {request.file_path}")
        pdf_content = minio_service.download_file(request.file_path, request.bucket_name)
        logger.info(f"Downloaded {len(pdf_content)} bytes from MinIO")
        
        # Извлекаем имя файла из пути
        filename = request.file_path.split('/')[-1]
        
        # Извлекаем таблицы из PDF
        logger.info("Extracting tables from PDF using tabula...")
        tables = process_pdf_to_rows(pdf_content, filename)
        logger.info(f"Extracted {len(tables)} tables from PDF")
        
        # Обрабатываем каждую таблицу
        results = []
        for i, table_data in enumerate(tables, 1):
            logger.info(f"Processing table {i}/{len(tables)}")
            
            try:
                # Запускаем проверку
                state = crew_cache.run(table_data)
                state = run_deterministic_calculator(state)
                
                results.append({
                    "table_index": i,
                    "status": "success",
                    "output": state.model_dump()
                })
                
            except Exception as e:
                logger.error(f"Error processing table {i}: {str(e)}")
                results.append({
                    "table_index": i,
                    "status": "error",
                    "error": str(e)
                })
        
        # Возвращаем результаты всех таблиц
        return {
            "source": "minio",
            "file_path": request.file_path,
            "bucket_name": request.bucket_name or minio_service.bucket_name,
            "filename": filename,
            "tables_processed": len(tables),
            "results": results
        }
        
    except MinioServiceException as exc:
        logger.error(f"MinIO error: {exc.message}", exc_info=True)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error processing PDF from MinIO: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(exc)}"
        ) from exc


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Health check endpoint для проверки состояния сервиса.
    """
    return {
        "status": "healthy",
        "service": "llm-smeta-pir",
        "crew_initialized": crew_cache is not None,
        "minio_configured": is_minio_configured()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )