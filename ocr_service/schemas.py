from pydantic import BaseModel, Field


class OCRPageInput(BaseModel):
    """Input model for a single page to be processed by OCR."""
    
    filename: str = Field(..., description="Original document filename")
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    image_base64: str = Field(..., description="Base64-encoded image data")


class OCRPageResult(BaseModel):
    """Result model for a processed OCR page."""
    
    filename: str = Field(..., description="Original document filename")
    page_number: int = Field(..., description="Page number (1-indexed)")
    extracted_text: str | None = Field(None, description="Extracted text content")
    success: bool = Field(..., description="Whether OCR processing succeeded")
    error: str | None = Field(None, description="Error message if processing failed")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class OCRBatchResult(BaseModel):
    """Result model for a batch of processed pages."""
    
    total_pages: int = Field(..., description="Total number of pages in batch")
    successful_pages: int = Field(..., description="Number of successfully processed pages")
    failed_pages: int = Field(..., description="Number of failed pages")
    total_processing_time_ms: float = Field(..., description="Total batch processing time")
    results: list[OCRPageResult] = Field(..., description="Individual page results")