import httpx
from bs4 import BeautifulSoup
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class WebExtractor:
    """Download single web page and extract clean text content."""

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds
        # Common user agent to avoid simple scraping blocks
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    async def extract_text_and_title(self, url: str) -> tuple[str, str]:
        """Fetch URL and extract the webpage's cleaned text and title.

        Args:
            url: The HTTP/HTTPS web page URL.

        Returns:
            A tuple of (extracted_text, page_title).
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
                html = response.text
        except Exception as e:
            logger.error(f"Failed to fetch website URL {url}: {e}", exc_info=True)
            raise ValueError(f"Failed to download webpage from {url}: {e}") from e

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title = soup.title.string.strip() if soup.title and soup.title.string else "Webpage Document"

            # Decompose boilerplate elements
            for element in soup(["script", "style", "header", "footer", "nav", "iframe", "noscript"]):
                element.decompose()

            # Extract cleaned text
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            # Remove empty blocks or multi-whitespace lines
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_text = "\n".join(chunk for chunk in chunks if chunk)

            if not cleaned_text.strip():
                raise ValueError("Web page has no readable text content.")

            return cleaned_text, title
        except Exception as e:
            logger.error(f"Failed to parse HTML from {url}: {e}", exc_info=True)
            raise ValueError(f"Failed to extract text from website: {e}") from e
