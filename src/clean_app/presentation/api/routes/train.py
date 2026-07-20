"""Unified Training API Router for training on FAQ, PDF, Website, and MongoDB Trips."""

from typing import Any
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, HttpUrl

from clean_app.application.use_cases.ingest_faq import FaqItem
from clean_app.presentation.api.schemas import FaqItemSchema

router = APIRouter(prefix="/train", tags=["train"])


class FaqIngestRequest(BaseModel):
    items: list[FaqItemSchema] = Field(
        ...,
        description="List of FAQ objects containing explicit 'question' and 'answer' fields."
    )


class WebsiteIngestRequest(BaseModel):
    url: HttpUrl = Field(..., description="The full HTTP/HTTPS URL of the webpage to train on.")


class TrainingResponseSchema(BaseModel):
    status: str
    source_type: str
    processed_count: int
    total_in_vector_store: int
    details: dict[str, Any] = Field(default_factory=dict)


@router.post("/faq", response_model=TrainingResponseSchema, status_code=status.HTTP_201_CREATED)
async def train_faq(request: Request, body: FaqIngestRequest) -> TrainingResponseSchema:
    """Train/index FAQ questions and answers into the vector store."""
    container = request.app.state.container
    try:
        faq_items = [
            FaqItem(
                question=item.question,
                answer=item.answer,
                category=item.category
            )
            for item in body.items
        ]
        res = container.ingest_faq.execute(faq_items)
        return TrainingResponseSchema(
            status="success",
            source_type="faq",
            processed_count=res.added_count,
            total_in_vector_store=res.total_in_store,
            details={"sample_ids": res.sample_ids},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during FAQ training: {e}",
        )


@router.post("/pdf", response_model=TrainingResponseSchema, status_code=status.HTTP_201_CREATED)
async def train_pdf(request: Request, file: UploadFile = File(...)) -> TrainingResponseSchema:
    """Train/index an uploaded PDF document into the vector store."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files (.pdf) are supported.",
        )

    container = request.app.state.container
    try:
        pdf_bytes = await file.read()
        res = container.ingest_pdf.execute(file.filename, pdf_bytes)
        return TrainingResponseSchema(
            status="success",
            source_type="pdf",
            processed_count=1,
            total_in_vector_store=res.total_in_store,
            details={"id": res.id, "title": res.title, "char_count": res.char_count},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during PDF training: {e}",
        )


@router.post("/website", response_model=TrainingResponseSchema, status_code=status.HTTP_201_CREATED)
async def train_website(request: Request, body: WebsiteIngestRequest) -> TrainingResponseSchema:
    """Download, extract text, and train/index a website URL into the vector store."""
    container = request.app.state.container
    try:
        url_str = str(body.url)
        res = await container.ingest_website.execute(url_str)
        return TrainingResponseSchema(
            status="success",
            source_type="website",
            processed_count=1,
            total_in_vector_store=res.total_in_store,
            details={"id": res.id, "title": res.title, "url": res.url, "char_count": res.char_count},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during website training: {e}",
        )


@router.post("/mongodb-trips", response_model=TrainingResponseSchema, status_code=status.HTTP_201_CREATED)
async def train_mongodb_trips(request: Request) -> TrainingResponseSchema:
    """Fetch live MongoDB trip data and train/index them into the vector store."""
    container = request.app.state.container
    try:
        res = await container.index_mongo_trips.execute()
        return TrainingResponseSchema(
            status="success",
            source_type="mongodb_trips",
            processed_count=res.indexed_count,
            total_in_vector_store=res.total_trips_in_store,
            details={"indexed_count": res.indexed_count},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during MongoDB trips training: {e}",
        )
