"""Durable, household-scoped identity for objects whose room is unknown.

A photo is associated with an existing object only by exact media identity, or
by the server-verified demo family's stable bytes. Uncertain user photos are
never merged based on object type or on probable species names.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from uuid import uuid4
from sqlalchemy import DateTime, ForeignKeyConstraint, Index, String, JSON, select
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def now():
    return datetime.now(timezone.utc)


class AutonomousObjectRecord(Base):
    __tablename__ = "autonomous_objects"
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    room_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_media_id: Mapped[str] = mapped_column(String(128), nullable=False)
    demo_family: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    identity_hint: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_autonomous_objects_household", "household_id", "kind"),)


class AutonomousObjectViewRecord(Base):
    __tablename__ = "autonomous_object_views"
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    media_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (ForeignKeyConstraint(["household_id", "object_id"],
        ["autonomous_objects.household_id", "autonomous_objects.id"]),)


def object_label(kind: str, room_label: str | None, index: int) -> str:
    unit = {"plant": "Plant", "appliance": "Appliance"}.get(kind, "Object")
    return f"{room_label or 'Household'} {unit} {index}"


class ObjectRegistry:
    def __init__(self, sessions):
        self.sessions = sessions

    def resolve(self, household_id: str, media_id: str, kind: str, demo_family: str | None = None,
                image_hash: str | None = None, evidence: list[str] | None = None,
                identity_hint: str | None = None):
        """Only call after independently corroborated visual claims support kind."""
        if kind not in {"plant", "appliance", "object"}:
            raise ValueError("Unsupported object kind")
        with self.sessions.begin() as db:
            previous = db.get(AutonomousObjectViewRecord, (household_id, media_id))
            if previous:
                obj = db.get(AutonomousObjectRecord, (household_id, previous.object_id))
                if obj is None or obj.kind != kind:
                    raise ValueError("Existing photo identity conflicts with new evidence")
                return obj.id
            matches = []
            if image_hash:
                matches = db.scalars(select(AutonomousObjectRecord).where(
                    AutonomousObjectRecord.household_id == household_id,
                    AutonomousObjectRecord.image_hash == image_hash,
                    AutonomousObjectRecord.kind == kind)).all()
            if not matches and demo_family:
                matches = db.scalars(select(AutonomousObjectRecord).where(
                    AutonomousObjectRecord.household_id == household_id,
                    AutonomousObjectRecord.demo_family == demo_family,
                    AutonomousObjectRecord.kind == kind)).all()
            if len(matches) > 1:
                raise ValueError("Ambiguous object identity")
            if matches:
                obj = matches[0]
            else:
                obj = AutonomousObjectRecord(household_id=household_id, id=str(uuid4()), kind=kind,
                    room_id=None, reference_media_id=media_id, demo_family=demo_family,
                    image_hash=image_hash, evidence=(evidence or [])[:12], identity_hint=identity_hint,
                    created_at=now(), updated_at=now())
                db.add(obj)
                db.flush()
            if evidence:
                obj.evidence = list(evidence)[:12]
                obj.updated_at = now()
            if identity_hint and not obj.identity_hint:
                obj.identity_hint = identity_hint[:120]
            db.add(AutonomousObjectViewRecord(household_id=household_id, media_id=media_id,
                object_id=obj.id, verified_at=now()))
            return obj.id

    def lookup(self, household_id: str, media_id: str, demo_family: str | None = None, image_hash: str | None = None):
        with self.sessions() as db:
            view = db.get(AutonomousObjectViewRecord, (household_id, media_id))
            if view:
                return view.object_id
            if image_hash:
                exact = db.scalars(select(AutonomousObjectRecord).where(
                    AutonomousObjectRecord.household_id == household_id,
                    AutonomousObjectRecord.image_hash == image_hash)).all()
                if len(exact) == 1: return exact[0].id
            if demo_family:
                objects = db.scalars(select(AutonomousObjectRecord).where(
                    AutonomousObjectRecord.household_id == household_id,
                    AutonomousObjectRecord.demo_family == demo_family)).all()
                if len(objects) == 1:
                    return objects[0].id
            return None

    def list(self, household_id: str):
        from app.services.autonomous_jobs import AutonomousRoomRecord
        with self.sessions() as db:
            objects = db.scalars(select(AutonomousObjectRecord).where(
                AutonomousObjectRecord.household_id == household_id).order_by(
                AutonomousObjectRecord.created_at, AutonomousObjectRecord.id)).all()
            rooms = {r.room_id: r.room_category for r in db.scalars(select(AutonomousRoomRecord).where(
                AutonomousRoomRecord.household_id == household_id)).all()}


            from app.services.autonomous_jobs import AutonomousScanJob
            views = db.scalars(select(AutonomousObjectViewRecord).where(
                AutonomousObjectViewRecord.household_id == household_id)).all()
            media_by_object = {}
            for view in views:
                media_by_object.setdefault(view.object_id, set()).add(view.media_id)
            all_media = {media for ids in media_by_object.values() for media in ids}
            research_by_media = {}
            research_by_object = {}
            if objects:


                jobs = db.scalars(select(AutonomousScanJob).where(
                    AutonomousScanJob.household_id == household_id,
                    AutonomousScanJob.state == 'completed')).all()
                known_objects = {obj.id for obj in objects}
                for job in jobs:
                    summary = job.review_summary or {}
                    automatic = summary.get('automatic_coordination') or {}
                    if not isinstance(automatic, dict):
                        continue
                    entries = [entry for entry in automatic.get('scene_research') or []
                        if isinstance(entry, dict)]
                    if job.media_id in all_media:
                        research_by_media.setdefault(job.media_id, []).extend(entries)
                    object_id = summary.get('object_id')
                    if object_id in known_objects:
                        research_by_object.setdefault(object_id, []).extend(entries)
            counts = {}
            result = []
            for obj in objects:
                key = (obj.room_id, obj.kind)
                counts[key] = counts.get(key, 0) + 1
                room_name = rooms.get(obj.room_id) if obj.room_id else None
                topic = 'plant_care' if obj.kind == 'plant' else 'appliance_guidance' if obj.kind == 'appliance' else None
                research = []


                research_entries = list(research_by_object.get(obj.id, []))
                for media_id in media_by_object.get(obj.id, {obj.reference_media_id}):
                    research_entries.extend(research_by_media.get(media_id, []))
                for entry in research_entries:
                    if entry.get('topic') != topic:
                        continue
                    for source in entry.get('sources') or []:
                        if isinstance(source, dict) and str(source.get('url', '')).startswith('https://'):
                            research.append({'title': str(source.get('title') or '')[:160],
                                'url': str(source['url'])[:1000],
                                'excerpt': str(source.get('excerpt') or '')[:240]})

                unique_sources = list({item['url']: item for item in research}.values())[:4]
                result.append({"id": obj.id, "kind": obj.kind,
                    "name": object_label(obj.kind, room_name, counts[key]),
                    "room_id": obj.room_id, "location_confirmed": obj.room_id is not None,
                    "reference_media_id": obj.reference_media_id,
                    "identity_hint": obj.identity_hint,
                    "identity_status": "possible" if obj.identity_hint else "unknown",
                    "catalog_candidate": None,
                    "catalog_reference": None,
                    "research_sources": unique_sources,
                    "evidence": list(obj.evidence or [])[:12],
                    "created_at": obj.created_at.isoformat()})
            return result

    def set_room(self, household_id: str, object_id: str, room_id: str | None):
        from app.services.autonomous_jobs import AutonomousRoomRecord
        with self.sessions.begin() as db:
            obj = db.get(AutonomousObjectRecord, (household_id, object_id))
            if obj is None:
                raise LookupError("Object not found")
            if room_id is not None and db.get(AutonomousRoomRecord, (household_id, room_id)) is None:
                raise LookupError("Room not found")
            obj.room_id = room_id
            obj.updated_at = now()
        return {"id": object_id, "room_id": room_id}
