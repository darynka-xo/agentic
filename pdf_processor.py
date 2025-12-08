"""
PDF Processor - автоматическое извлечение таблиц из PDF
"""
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import tabula
import logging

logger = logging.getLogger(__name__)


def extract_tables_from_pdf(pdf_content: bytes, filename: str = "upload.pdf") -> List[Dict[str, Any]]:
    """
    Извлекает таблицы из PDF и конвертирует в формат для обработки.
    
    Args:
        pdf_content: Содержимое PDF файла в байтах
        filename: Имя файла (для логирования)
    
    Returns:
        Список табличных данных в формате tabula JSON
    """
    logger.info(f"Processing PDF: {filename}")
    
    # Сохраняем PDF во временный файл
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(pdf_content)
        tmp_path = tmp_file.name
    
    try:
        # Извлекаем таблицы используя tabula
        # lattice=True для таблиц с видимыми границами
        tables = tabula.read_pdf(
            tmp_path,
            pages='all',
            lattice=True,
            pandas_options={'header': None}  # Без заголовков
        )
        
        logger.info(f"Extracted {len(tables)} tables from PDF")
        
        # Конвертируем pandas DataFrames в наш формат
        result_tables = []
        
        for i, df in enumerate(tables, 1):
            # Конвертируем DataFrame в список строк
            rows = []
            for _, row in df.iterrows():
                # Конвертируем значения в строки
                row_data = [str(val) if val is not None and str(val) != 'nan' else '' 
                           for val in row.values]
                rows.append(row_data)
            
            # Формат совместимый с текущим preprocessor
            table_data = {
                "file": filename,
                "relative_path": filename,
                "table_index": i,
                "rows": rows,
                "shape": [len(rows), len(rows[0]) if rows else 0],
                "columns": [f"Col{j}" for j in range(len(rows[0]) if rows else 0)]
            }
            
            result_tables.append(table_data)
        
        logger.info(f"Successfully processed {len(result_tables)} tables")
        return result_tables
        
    finally:
        # Удаляем временный файл
        Path(tmp_path).unlink(missing_ok=True)


def process_pdf_to_rows(pdf_content: bytes, filename: str = "upload.pdf") -> List[Dict[str, Any]]:
    """
    Обрабатывает PDF и возвращает список строк для проверки.
    Каждая таблица = отдельный payload.
    
    Returns:
        Список payloads готовых для отправки в /predict
    """
    tables = extract_tables_from_pdf(pdf_content, filename)
    
    payloads = []
    for table in tables:
        # Каждая таблица - отдельный payload
        payloads.append(table)
    
    return payloads
