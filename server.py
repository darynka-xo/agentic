from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Body, FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel, Field

from agents import build_crew
from config import get_db
from core.calculator import run_deterministic_calculator
from pdf_processor import process_pdf_to_rows
from ocr_pdf_processor import process_pdf_to_rows_with_ocr

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logging.warning("PyMuPDF (fitz) not available, PDF text detection will be limited")
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


def detect_pdf_type(pdf_content: bytes, text_threshold: int = 100) -> Tuple[bool, int]:
    """
    Определяет тип PDF: цифровой (digital) или отсканированный (scanned).
    
    Args:
        pdf_content: Содержимое PDF файла в байтах
        text_threshold: Минимальное количество символов для определения как цифровой PDF
    
    Returns:
        Tuple[is_digital, total_chars]: (True если цифровой PDF, общее количество символов)
    """
    if not FITZ_AVAILABLE:
        logger.warning("PyMuPDF (fitz) not available, assuming digital PDF")
        return True, 0
    
    try:
        # Открываем PDF напрямую из bytes
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        
        total_chars = 0
        # Проверяем первые несколько страниц для оптимизации
        pages_to_check = min(3, len(doc))
        
        for page_num in range(pages_to_check):
            page = doc[page_num]
            text = page.get_text()
            
            if text:
                # Считаем только буквенно-цифровые символы
                chars = len([c for c in text if c.isalnum()])
                total_chars += chars
        
        doc.close()
        
        is_digital = total_chars >= text_threshold
        
        logger.info(
            f"PDF type detection: {total_chars} characters found, "
            f"classified as {'DIGITAL' if is_digital else 'SCANNED'}"
        )
        
        return is_digital, total_chars
        
    except Exception as e:
        logger.error(f"Error detecting PDF type: {e}, assuming digital PDF")
        return True, 0


app = FastAPI(title="Estimate Validator API")
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
    Endpoint for uploading PDF files.
    Automatically detects if PDF is digital or scanned and routes accordingly:
    - Digital PDFs (>100 chars): Uses tabula for table extraction
    - Scanned PDFs (<=100 chars): Uses VLM OCR for table extraction
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
        
        # Определяем тип PDF
        is_digital, char_count = detect_pdf_type(pdf_content)
        
        # Выбираем метод обработки
        if is_digital:
            logger.info(f"PDF is DIGITAL ({char_count} chars), using tabula...")
            tables = process_pdf_to_rows(pdf_content, file.filename)
            processing_method = "tabula"
        else:
            logger.info(f"PDF is SCANNED ({char_count} chars), using VLM OCR...")
            tables = await process_pdf_to_rows_with_ocr(pdf_content, file.filename)
            processing_method = "vlm_ocr"
        
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
            "pdf_type": "digital" if is_digital else "scanned",
            "character_count": char_count,
            "processing_method": processing_method,
            "tables_processed": len(tables),
            "results": results
        }
        
    except Exception as exc:
        logger.error(f"Error processing PDF: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(exc)}") from exc


@app.post("/predict_pdf_ocr")
async def predict_pdf_ocr(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    FORCE OCR-based PDF processing using VLM.
    Use this endpoint to force OCR processing regardless of PDF type.
    For automatic detection, use /predict_pdf instead.
    """
    logger.info(f"Received PDF upload for OCR processing: {file.filename}")
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
    
    # Проверяем что это PDF
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Читаем содержимое файла
        pdf_content = await file.read()
        logger.info(f"Read {len(pdf_content)} bytes from PDF")
        
        # Извлекаем таблицы из PDF используя OCR
        logger.info("Extracting tables from PDF using VLM OCR...")
        tables = await process_pdf_to_rows_with_ocr(pdf_content, file.filename)
        logger.info(f"Extracted {len(tables)} tables from PDF via OCR")
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
                    "page_number": table_data.get("page_number", i),
                    "status": "success",
                    "output": state.model_dump(),
                    "ocr_metadata": table_data.get("ocr_metadata", {})
                })
                
            except Exception as e:
                logger.error(f"Error processing table {i}: {str(e)}")
                results.append({
                    "table_index": i,
                    "page_number": table_data.get("page_number", i),
                    "status": "error",
                    "error": str(e)
                })
        
        # Возвращаем результаты всех таблиц
        return {
            "filename": file.filename,
            "processing_method": "vlm_ocr",
            "source": "minio",
            "file_path": request.file_path,
            "bucket_name": request.bucket_name or minio_service.bucket_name,
            "filename": filename,
            "tables_processed": len(tables),
            "results": results
        }
        
    except Exception as exc:
        logger.error(f"Error processing PDF with OCR: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR PDF processing failed: {str(exc)}") from exc
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