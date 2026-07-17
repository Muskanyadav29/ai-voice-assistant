import io
import pypdf
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class PdfExtractor:
    """Extract text content from PDF binary data."""

    def extract_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF pages and return combined string.

        Args:
            pdf_bytes: The raw bytes of the PDF file.
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                else:
                    logger.debug(f"No extractable text found on page {i + 1}")

            extracted_text = "\n".join(text_parts).strip()
            if not extracted_text:
                raise ValueError("PDF does not contain any extractable text.")
            return extracted_text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            raise ValueError(f"Failed to parse PDF file: {e}") from e
