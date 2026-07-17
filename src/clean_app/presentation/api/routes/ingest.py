from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, HttpUrl


router = APIRouter(prefix="/ingest", tags=["ingest"])


class WebsiteIngestRequest(BaseModel):
    url: HttpUrl = Field(..., description="The full HTTP/HTTPS URL of the webpage to extract and index.")


class IngestResponseSchema(BaseModel):
    id: str
    title: str
    url: str
    char_count: int
    total_in_store: int


@router.post("/website", response_model=IngestResponseSchema, status_code=status.HTTP_201_CREATED)
async def ingest_website(request: Request, body: WebsiteIngestRequest) -> IngestResponseSchema:
    """Download, extract text, and index a single website page into the vector store."""
    container = request.app.state.container
    try:
        # Convert Pydantic HttpUrl to string
        url_str = str(body.url)
        result = await container.ingest_website.execute(url_str)
        return IngestResponseSchema(
            id=result.id,
            title=result.title,
            url=result.url,
            char_count=result.char_count,
            total_in_store=result.total_in_store,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during website ingestion: {e}",
        )


@router.post("/pdf", response_model=IngestResponseSchema, status_code=status.HTTP_201_CREATED)
async def ingest_pdf(request: Request, file: UploadFile = File(...)) -> IngestResponseSchema:
    """Extract text from an uploaded PDF and index it into the vector store."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files (.pdf) are supported.",
        )

    container = request.app.state.container
    try:
        pdf_bytes = await file.read()
        result = container.ingest_pdf.execute(file.filename, pdf_bytes)
        return IngestResponseSchema(
            id=result.id,
            title=result.title,
            url=result.url,
            char_count=result.char_count,
            total_in_store=result.total_in_store,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during PDF ingestion: {e}",
        )


@router.post("/image", response_model=IngestResponseSchema, status_code=status.HTTP_201_CREATED)
async def ingest_image(request: Request, file: UploadFile = File(...)) -> IngestResponseSchema:
    """Transcribe text from an uploaded image using vision LLM and index it into the vector store."""
    content_type = file.content_type or "image/jpeg"
    if not (
        content_type.startswith("image/")
        or file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Supported image types: .jpg, .jpeg, .png, .webp",
        )

    container = request.app.state.container
    try:
        image_bytes = await file.read()
        result = await container.ingest_image.execute(file.filename, image_bytes, content_type)
        return IngestResponseSchema(
            id=result.id,
            title=result.title,
            url=result.url,
            char_count=result.char_count,
            total_in_store=result.total_in_store,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during image ingestion: {e}",
        )
