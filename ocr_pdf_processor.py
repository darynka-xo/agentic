"""
OCR-based PDF Processor - извлечение таблиц через VLM OCR
"""
import asyncio
import base64
import logging
from pathlib import Path
from typing import Dict, Any, List
import tempfile

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber not available, OCR-based PDF processing will be limited")

from ocr_service.vlm_ocr import VLMOCR
from ocr_service.schemas import OCRPageInput

logger = logging.getLogger(__name__)


async def extract_tables_from_pdf_with_ocr(
    pdf_content: bytes, 
    filename: str = "upload.pdf"
) -> List[Dict[str, Any]]:
    """
    Извлекает таблицы из PDF используя VLM OCR.
    
    Args:
        pdf_content: Содержимое PDF файла в байтах
        filename: Имя файла (для логирования)
    
    Returns:
        Список табличных данных
    """
    logger.info(f"Processing PDF with OCR: {filename}")
    
    if not PDFPLUMBER_AVAILABLE:
        raise RuntimeError("pdfplumber is required for OCR-based PDF processing")
    
    # Сохраняем PDF во временный файл
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(pdf_content)
        tmp_path = tmp_file.name
    
    try:
        # Открываем PDF и конвертируем страницы в изображения
        ocr_pages = []
        with pdfplumber.open(tmp_path) as pdf:
            logger.info(f"PDF has {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, start=1):
                # Конвертируем страницу в изображение
                img = page.to_image(resolution=200)
                
                # Получаем bytes изображения
                img_bytes = img.original.tobytes('png')
                
                # Кодируем в base64
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                ocr_pages.append(OCRPageInput(
                    filename=filename,
                    page_number=page_num,
                    image_base64=img_base64
                ))
        
        # Обрабатываем все страницы через OCR
        logger.info(f"Running OCR on {len(ocr_pages)} pages...")
        async with VLMOCR() as ocr:
            batch_result = await ocr.process_batch(ocr_pages)
        
        logger.info(
            f"OCR complete: {batch_result.successful_pages}/{batch_result.total_pages} "
            f"pages successful in {batch_result.total_processing_time_ms:.2f}ms"
        )
        
        # Парсим OCR результаты и конвертируем в формат таблиц
        result_tables = []
        for page_result in batch_result.results:
            if not page_result.success or not page_result.extracted_text:
                logger.warning(
                    f"Page {page_result.page_number} OCR failed: {page_result.error}"
                )
                continue
            
            # Парсим текст в строки (простая реализация)
            # Можно улучшить парсинг markdown таблиц
            rows = _parse_ocr_text_to_rows(page_result.extracted_text)
            
            if rows:
                table_data = {
                    "file": filename,
                    "relative_path": filename,
                    "table_index": page_result.page_number,
                    "page_number": page_result.page_number,
                    "rows": rows,
                    "shape": [len(rows), len(rows[0]) if rows else 0],
                    "columns": [f"Col{j}" for j in range(len(rows[0]) if rows else 0)],
                    "ocr_metadata": {
                        "processing_time_ms": page_result.processing_time_ms,
                        "raw_text": page_result.extracted_text
                    }
                }
                result_tables.append(table_data)
        
        logger.info(f"Successfully processed {len(result_tables)} tables from OCR")
        return result_tables
        
    finally:
        # Удаляем временный файл
        Path(tmp_path).unlink(missing_ok=True)


def _parse_ocr_text_to_rows(text: str) -> List[List[str]]:
    """
    Парсит OCR текст в строки таблицы.
    Простая реализация - можно улучшить для markdown таблиц.
    
    Args:
        text: Извлеченный OCR текст
    
    Returns:
        Список строк таблицы
    """
    rows = []
    
    # Разбиваем на строки
    lines = text.strip().split('\n')
    
    for line in lines:
        # Пропускаем пустые строки и markdown разделители
        if not line.strip() or line.strip().startswith('---') or line.strip().startswith('==='):
            continue
        
        # Если строка содержит '|' - это markdown таблица
        if '|' in line:
            # Парсим markdown table row
            cells = [cell.strip() for cell in line.split('|')]
            # Убираем пустые начальные/конечные элементы
            cells = [c for c in cells if c]
            if cells:
                rows.append(cells)
        else:
            # Иначе - разбиваем по пробелам/табам
            cells = line.split()
            if cells:
                rows.append(cells)
    
    return rows


async def process_pdf_to_rows_with_ocr(
    pdf_content: bytes, 
    filename: str = "upload.pdf"
) -> List[Dict[str, Any]]:
    """
    Обрабатывает PDF через OCR и возвращает список строк для проверки.
    
    Returns:
        Список payloads готовых для отправки в /predict
    """
    tables = await extract_tables_from_pdf_with_ocr(pdf_content, filename)
    
    payloads = []
    for table in tables:
        # Каждая таблица - отдельный payload
        payloads.append(table)
    
    return payloads
