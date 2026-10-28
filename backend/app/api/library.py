import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Collection, CollectionItem, Feedback, Moment, Video
from app.services import video_dir
from app.services.present import load_evaluation, moment_out

router = APIRouter(prefix="/api", tags=["library"])


class MomentIn(BaseModel):
    video_id: uuid.UUID
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    note: str = ""
    query: str = ""


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class CollectionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ItemIn(BaseModel):
    moment_id: uuid.UUID


class FeedbackIn(BaseModel):
    video_id: uuid.UUID
    segment_id: uuid.UUID
    query: str = Field(min_length=1, max_length=500)
    mode: Literal["all", "speech", "screen_text", "visual"]
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    relevant: bool


def _thumb(video_id: uuid.UUID) -> str | None:
    if (video_dir(video_id) / "thumb.jpg").is_file():
        return f"/api/videos/{video_id}/thumbnail"
    return None


def _moment_payload(db: Session, moment: Moment) -> dict:
    video = db.get(Video, moment.video_id)
    title = video.title if video else "Deleted video"
    return moment_out(moment, title, _thumb(moment.video_id) if video else None)


@router.get("/moments")
def list_moments(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Moment).order_by(Moment.created_at.desc())))
    return {"items": [_moment_payload(db, moment) for moment in rows]}


@router.post("/moments", status_code=201)
def create_moment(body: MomentIn, db: Session = Depends(get_db)):
    if body.end_sec <= body.start_sec:
        raise AppError(400, "bad_range", "The end time has to be after the start time.")
    video = db.get(Video, body.video_id)
    if video is None:
        raise AppError(404, "not_found", "That video does not exist.")
    moment = Moment(
        video_id=body.video_id,
        start_sec=body.start_sec,
        end_sec=body.end_sec,
        title=body.title.strip(),
        note=body.note.strip(),
        query=body.query.strip(),
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)
    return _moment_payload(db, moment)


@router.delete("/moments/{moment_id}", status_code=204)
def delete_moment(moment_id: uuid.UUID, db: Session = Depends(get_db)):
    moment = db.get(Moment, moment_id)
    if moment is None:
        raise AppError(404, "not_found", "That moment does not exist.")
    db.delete(moment)
    db.commit()


@router.get("/collections")
def list_collections(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Collection).order_by(Collection.created_at.desc())))
    payload = []
    for collection in rows:
        count = int(
            db.scalar(
                select(func.count()).select_from(CollectionItem).where(CollectionItem.collection_id == collection.id)
            )
            or 0
        )
        payload.append(
            {
                "id": str(collection.id),
                "name": collection.name,
                "description": collection.description,
                "created_at": collection.created_at.isoformat() if collection.created_at else None,
                "item_count": count,
            }
        )
    return {"items": payload}


@router.post("/collections", status_code=201)
def create_collection(body: CollectionIn, db: Session = Depends(get_db)):
    collection = Collection(name=body.name.strip(), description=body.description.strip())
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return {
        "id": str(collection.id),
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at.isoformat() if collection.created_at else None,
        "item_count": 0,
    }


@router.patch("/collections/{collection_id}")
def update_collection(collection_id: uuid.UUID, body: CollectionPatch, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise AppError(404, "not_found", "That collection does not exist.")
    if body.name is not None:
        collection.name = body.name.strip()
    if body.description is not None:
        collection.description = body.description.strip()
    db.commit()
    return {"id": str(collection.id), "name": collection.name, "description": collection.description}


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: uuid.UUID, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise AppError(404, "not_found", "That collection does not exist.")
    db.execute(delete(CollectionItem).where(CollectionItem.collection_id == collection_id))
    db.delete(collection)
    db.commit()


@router.get("/collections/{collection_id}")
def get_collection(collection_id: uuid.UUID, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise AppError(404, "not_found", "That collection does not exist.")
    links = list(
        db.scalars(select(CollectionItem).where(CollectionItem.collection_id == collection_id))
    )
    moments = []
    for link in links:
        moment = db.get(Moment, link.moment_id)
        if moment is not None:
            moments.append(_moment_payload(db, moment))
    return {
        "id": str(collection.id),
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at.isoformat() if collection.created_at else None,
        "item_count": len(moments),
        "items": moments,
    }


@router.post("/collections/{collection_id}/items", status_code=201)
def add_item(collection_id: uuid.UUID, body: ItemIn, db: Session = Depends(get_db)):
    if db.get(Collection, collection_id) is None:
        raise AppError(404, "not_found", "That collection does not exist.")
    if db.get(Moment, body.moment_id) is None:
        raise AppError(404, "not_found", "That moment does not exist.")
    existing = db.get(CollectionItem, {"collection_id": collection_id, "moment_id": body.moment_id})
    if existing is None:
        db.add(CollectionItem(collection_id=collection_id, moment_id=body.moment_id))
        db.commit()
    return {"collection_id": str(collection_id), "moment_id": str(body.moment_id)}


@router.delete("/collections/{collection_id}/items/{moment_id}", status_code=204)
def remove_item(collection_id: uuid.UUID, moment_id: uuid.UUID, db: Session = Depends(get_db)):
    db.execute(
        delete(CollectionItem).where(
            CollectionItem.collection_id == collection_id, CollectionItem.moment_id == moment_id
        )
    )
    db.commit()


@router.post("/feedback", status_code=201)
def create_feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    if db.get(Video, body.video_id) is None:
        raise AppError(404, "not_found", "That video does not exist.")
    if body.end_sec <= body.start_sec:
        raise AppError(400, "bad_range", "The end time has to be after the start time.")
    row = Feedback(
        video_id=body.video_id,
        segment_id=body.segment_id,
        query=body.query.strip(),
        mode=body.mode,
        start_sec=body.start_sec,
        end_sec=body.end_sec,
        relevant=body.relevant,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "relevant": row.relevant}


@router.get("/evaluation")
def evaluation():
    return load_evaluation()
