import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import Sequence

from ocr_service.ocr_prompts import OCR_BASE_PROMPT
from ocr_service.schemas import OCRPageInput, OCRPageResult, OCRBatchResult

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Configure module logger
logger = logging.getLogger(__name__)


from dotenv import load_dotenv
load_dotenv()

class VLMOCR:
    """
    High-throughput async OCR processor using Vision Language Models.
    
    This class manages batch processing of document images through an
    OpenAI-compatible API with semaphore-controlled concurrency and
    automatic retry logic for resilience.
    
    Configuration is read from environment variables:
        - OPENAI_API_BASE: vLLM server URL (required)
        - OPENAI_API_KEY: API key (required, can be dummy for vLLM)
        - OCR_MODEL_NAME: Model identifier (required)
        - OCR_MAX_CONCURRENCY: Max parallel requests (default: 10)
        - OCR_MAX_RETRIES: Retry attempts per page (default: 3)
        - OCR_TIMEOUT_SECONDS: Request timeout (default: 60)
    
    Example:
        ```python
        ocr = VLMOCR()
        pages = [
            OCRPageInput(filename="doc.pdf", page_number=1, image_base64="..."),
            OCRPageInput(filename="doc.pdf", page_number=2, image_base64="..."),
        ]
        results = await ocr.process_batch(pages)
        ```
    """
    
    def __init__(self) -> None:        
        self._api_base = os.getenv("OPENAI_API_BASE")
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._model_name = os.getenv("OCR_MODEL_NAME")
        self._max_concurrency = int(os.getenv("OCR_MAX_CONCURRENCY", 16))
        self._max_retries = int(os.getenv("OCR_MAX_RETRIES", 3))
        self._timeout_seconds = int(os.getenv("OCR_TIMEOUT_SECONDS", 60))
        self._max_tokens = int(os.getenv("OCR_MAX_TOKENS", 16384))
        self._temperature = float(os.getenv("OCR_TEMPERATURE", 0.0))
        self._ocr_prompt = OCR_BASE_PROMPT
        
        self._client = AsyncOpenAI(
            base_url=self._api_base,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
        )
        
        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        
        logger.info(
            f"VLMOCR initialized: model={self._model_name}, "
            f"max_concurrency={self._max_concurrency}, "
            f"max_retries={self._max_retries}, "
            f"timeout={self._timeout_seconds}s"
        )
    
    async def _call_ocr_api(self, image_base64: str) -> str:
        """
        Make a single OCR API call.
        
        Args:
            image_base64: Base64-encoded image data
            
        Returns:
            Extracted text from the image
            
        Raises:
            Exception: On API errors (will be retried by caller)
        """

        if image_base64.startswith("/9j/"):
            media_type = "image/jpeg"
        elif image_base64.startswith("iVBOR"):
            media_type = "image/png"
        elif image_base64.startswith("R0lGOD"):
            media_type = "image/gif"
        elif image_base64.startswith("UklGR"):
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
        
        response = await self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._ocr_prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_base64}",
                            },
                        },
                    ],
                }
            ],
            max_completion_tokens=self._max_tokens,
            temperature=self._temperature
        )
        
        if not response.choices:
            raise RuntimeError("API returned empty choices list")
        
        return response.choices[0].message.content or ""
    
    async def _process_single_page(self, page: OCRPageInput) -> OCRPageResult:
        """
        Process a single page with retry logic and semaphore control.
        
        Args:
            page: Input page data
            
        Returns:
            OCR result for the page (success or failure)
        """
        @retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _call_with_retry() -> str:
            try:
                return await self._call_ocr_api(page.image_base64)
            except Exception as e:
                logger.error(
                    f"Failed to process page: filename={page.filename}, "
                    f"page={page.page_number}, error={e}"
                )
                raise e
        
        async with self._semaphore:
            start_time = time.perf_counter()
            logger.debug(f"Processing page: filename={page.filename}, page={page.page_number}")
            
            try:
                extracted_text = await _call_with_retry()
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                logger.debug(
                    f"Successfully processed: filename={page.filename}, "
                    f"page={page.page_number}, time={elapsed_ms:.2f}ms"
                )
                
                return OCRPageResult(
                    filename=page.filename,
                    page_number=page.page_number,
                    extracted_text=extracted_text,
                    success=True,
                    error=None,
                    processing_time_ms=elapsed_ms,
                )
                
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                error_msg = f"{type(e).__name__}: {str(e)}"
                
                logger.error(
                    f"Failed to process page after {self._max_retries} retries: "
                    f"filename={page.filename}, page={page.page_number}, error={error_msg}"
                )
                
                return OCRPageResult(
                    filename=page.filename,
                    page_number=page.page_number,
                    extracted_text=None,
                    success=False,
                    error=error_msg,
                    processing_time_ms=elapsed_ms,
                )
    
    async def process_batch(
        self,
        pages: Sequence[OCRPageInput],
    ) -> OCRBatchResult:
        """
        Process a batch of pages.
        
        Args:
            pages: Sequence of pages to process
            
        Returns:
            Batch result containing all page results
        """
        if not pages:
            logger.warning("Empty batch received, returning empty result")
            return OCRBatchResult(
                total_pages=0,
                successful_pages=0,
                failed_pages=0,
                total_processing_time_ms=0.0,
                results=[],
            )
        
        logger.info(
            f"Starting batch processing: {len(pages)} pages, "
            f"max_concurrency={self._max_concurrency}"
        )
        
        batch_start_time = time.perf_counter()
    
        tasks = [self._process_single_page(page) for page in pages]
        results = await asyncio.gather(*tasks)
        
        batch_elapsed_ms = (time.perf_counter() - batch_start_time) * 1000
        
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count
        
        logger.info(
            f"Batch processing complete: {len(pages)} pages, "
            f"{successful_count} successful, {failed_count} failed, "
            f"total_time={batch_elapsed_ms:.2f}ms"
        )
        
        return OCRBatchResult(
            total_pages=len(results),
            successful_pages=successful_count,
            failed_pages=failed_count,
            total_processing_time_ms=batch_elapsed_ms,
            results=list(results),
        )
    
    @staticmethod
    def image_to_base64(image_source: str | Path | bytes) -> str:
        """
        Convert an image to Base64-encoded string.
        
        Args:
            image_source: Either a file path (str or Path) or raw image bytes
            
        Returns:
            Base64-encoded string of the image data
            
        Raises:
            FileNotFoundError: If the file path does not exist
            ValueError: If the image source type is not supported
        """
        if isinstance(image_source, bytes):
            return base64.b64encode(image_source).decode("utf-8")
        
        if isinstance(image_source, (str, Path)):
            path = Path(image_source)
            if not path.exists():
                raise FileNotFoundError(f"Image file not found: {path}")
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        
        raise ValueError(f"Unsupported image source type: {type(image_source).__name__}")
    
    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
        logger.info("VLMOCR client closed")
    
    async def __aenter__(self) -> "VLMOCR":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

