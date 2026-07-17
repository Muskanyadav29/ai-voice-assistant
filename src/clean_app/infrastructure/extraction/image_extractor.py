import base64
from clean_app.infrastructure.config.settings import Settings
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class ImageExtractor:
    """Extract text from images using OpenAI's gpt-4o-mini vision capabilities."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._openai_key = settings.openai_api_key
        self._model = settings.openai_model or "gpt-4o-mini"

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Call OpenAI multimodal chat completion to transcribe text from an image.

        Args:
            image_bytes: Raw bytes of the image file.
            mime_type: MIME type of the image, e.g., image/jpeg or image/png.
        """
        if not self._openai_key:
            logger.warning("No OpenAI API key configured. Cannot run vision extraction on image.")
            raise ValueError(
                "OpenAI API key is missing. Image text extraction requires an active API key."
            )

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._openai_key)

            # Base64 encode the image
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Request description and text transcription from GPT-4o-mini
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an OCR and document analyst system. Extract all readable text "
                                    "verbatim from this image, preserving original layout/paragraphs where possible. "
                                    "If the image contains objects, scenes, or diagrams with sparse text, transcribe the text "
                                    "and also write a short paragraph describing the image content. "
                                    "Return only the extracted text/description, with no conversational preamble or markdown code blocks."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=2000,
            )
            extracted_text = response.choices[0].message.content
            if not extracted_text:
                raise ValueError("OpenAI returned an empty response.")
            return extracted_text.strip()
        except Exception as e:
            logger.error(f"Error calling OpenAI vision API for image extraction: {e}", exc_info=True)
            raise ValueError(f"Failed to extract text from image: {e}") from e
