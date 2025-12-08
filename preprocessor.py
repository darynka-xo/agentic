"""
Preprocessor to convert tabula JSON format to simple text format for LLM.
"""

from typing import Any, Dict, List


def extract_text_from_tabula_row(row: List[str]) -> str:
    """Extract text from a single tabula row."""
    # Join non-empty cells with spaces
    text = " ".join(cell.strip() for cell in row if cell and cell.strip())
    # Clean up \r and multiple spaces
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = ' '.join(text.split())  # Remove multiple spaces
    return text


def tabula_to_simple_format(tabula_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert tabula JSON format to simple format expected by LLM.
    
    Tabula format:
    {
        "file": "...",
        "rows": [[cell1, cell2, ...], ...],
        "columns": [...],
        "table_index": 1
    }
    
    Simple format:
    {
        "raw_text": "extracted text from row",
        "row_index": 0,
        "page_number": 1
    }
    """
    # Check if it's already in simple format
    if "raw_text" in tabula_payload:
        return tabula_payload
    
    # Extract rows from tabula format
    rows = tabula_payload.get("rows", [])
    if not rows:
        return {
            "raw_text": "",
            "row_index": 0,
            "page_number": tabula_payload.get("table_index", 1)
        }
    
    # Convert rows to text, skipping headers/empty rows
    all_text = []
    for idx, row in enumerate(rows):
        row_text = extract_text_from_tabula_row(row)
        
        # Skip header rows (usually numbers, empty, or section titles)
        if not row_text:
            continue
        if row_text.strip() in ["1", "2", "3", "4", "5"]:  # Header numbers
            continue
        if len(row_text.split()) < 3:  # Too short to be useful
            continue
        if "Проектные работы" in row_text and len(row_text) < 50:  # Section headers
            continue
            
        all_text.append(row_text)
    
    # Join rows with newline for better readability
    combined_text = " | ".join(all_text)
    
    return {
        "raw_text": combined_text,
        "row_index": 0,
        "page_number": tabula_payload.get("table_index", 1),
        "original_file": tabula_payload.get("relative_path", ""),
    }


def preprocess_tabula_payload(tabula_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main preprocessing function.
    Converts tabula format to simple format if needed.
    """
    return tabula_to_simple_format(tabula_payload)

