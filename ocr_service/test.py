import asyncio
import io
import logging
from pathlib import Path

import pdfplumber

from dotenv import load_dotenv
load_dotenv()

from ocr_service.schemas import OCRPageInput
from vlm_ocr import VLMOCR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# PDF file to process (in the same directory as this script)
PDF_FILENAME = "test.pdf"
DPI = 100


def pdf_to_page_inputs(pdf_path: Path) -> list[OCRPageInput]:
    """
    Read a PDF file and convert each page to OCRPageInput.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of OCRPageInput objects, one per page
    """
    page_inputs = []
    
    with pdfplumber.open(pdf_path) as pdf:
        logger.info(f"Opened PDF: {pdf_path.name}, {len(pdf.pages)} pages")
        
        for page_num, page in enumerate(pdf.pages, start=1):
            # Convert page to image at specified DPI
            page_image = page.to_image(resolution=DPI)
            
            # Convert PIL image to bytes (PNG format)
            img_buffer = io.BytesIO()
            page_image.original.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()
            
            # Convert to base64
            image_base64 = VLMOCR.image_to_base64(img_bytes)
            
            page_input = OCRPageInput(
                filename=pdf_path.name,
                page_number=page_num,
                image_base64=image_base64
            )
            page_inputs.append(page_input)
            logger.info(f"Prepared page {page_num}/{len(pdf.pages)}")
    
    return page_inputs


async def main():
    # Resolve path relative to this script's directory
    script_dir = Path(__file__).parent
    pdf_path = script_dir / PDF_FILENAME
    
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return
    
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Convert PDF pages to OCR inputs
    page_inputs = pdf_to_page_inputs(pdf_path)
    
    if not page_inputs:
        logger.warning("No pages found in PDF")
        return
    
    # Process with VLMOCR
    async with VLMOCR() as ocr:
        results = await ocr.process_batch(page_inputs)
    
    # Print results
    print("\n" + "=" * 60)
    print("OCR RESULTS")
    print("=" * 60)
    print(f"Total pages: {results.total_pages}")
    print(f"Successful: {results.successful_pages}")
    print(f"Failed: {results.failed_pages}")
    print(f"Total time: {results.total_processing_time_ms:.2f}ms")
    print("=" * 60 + "\n")
    
    for result in results.results:
        print(f"\n--- Page {result.page_number} ---")
        if result.success:
            print(f"Processing time: {result.processing_time_ms:.2f}ms")
            print(f"Extracted text:\n{result.extracted_text}")
        else:
            print(f"ERROR: {result.error}")
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())

