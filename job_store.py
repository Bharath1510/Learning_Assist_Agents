import os
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
except ImportError:  # pragma: no cover - depends on local environment
    ASCENDING = DESCENDING = MongoClient = None
    PyMongoError = ServerSelectionTimeoutError = Exception

DEFAULT_STAGE_DEFS = [
    ("queued", "Queued"),
    ("research", "Research"),
    ("writing", "Writing"),
    ("export", "Finalize"),
    ("complete", "Complete"),
]


class JobStoreError(RuntimeError):
    pass


class MongoJobStore:
    def __init__(self):
        # Local MongoDB (the same server MongoDB Compass connects to) by default.
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        # Friendly names so the data is easy to browse in Compass.
        self.database_name = os.getenv("MONGODB_DB", "study_notes_app")
        self.collection_name = os.getenv("MONGODB_NOTES_COLLECTION", "study_notes")
        self.stickies_collection_name = os.getenv("MONGODB_STICKIES_COLLECTION", "sticky_notes")
        self._client = None
        self._collection = None
        self._stickies = None

    def _connect(self):
        if MongoClient is None:
            raise JobStoreError(
                "pymongo is not installed. Install it with: python -m pip install pymongo"
            )

        if self._collection is not None:
            return self._collection

        try:
            self._client = MongoClient(self.mongodb_uri, serverSelectionTimeoutMS=2500)
            self._client.admin.command("ping")
            database = self._client[self.database_name]
            self._collection = database[self.collection_name]
            self._ensure_indexes()
        except ServerSelectionTimeoutError as exc:
            raise JobStoreError(
                f"Could not connect to MongoDB at {self.mongodb_uri}. Start MongoDB or update MONGODB_URI."
            ) from exc
        except PyMongoError as exc:
            raise JobStoreError(f"MongoDB error: {exc}") from exc

        return self._collection

    def _stickies_collection(self):
        if self._stickies is not None:
            return self._stickies

        self._connect()  # ensures client + reachable server
        self._stickies = self._client[self.database_name][self.stickies_collection_name]
        self._stickies.create_index([("note_id", ASCENDING), ("updated_at", DESCENDING)])
        return self._stickies

    def _ensure_indexes(self):
        self._collection.create_index([("created_at", DESCENDING)])
        self._collection.create_index([("status", ASCENDING), ("updated_at", DESCENDING)])
        self._collection.create_index([("topic", "text"), ("slug", "text")])

    def create_job(self, topic, slug):
        now = datetime.utcnow()
        job = {
            "_id": uuid.uuid4().hex,
            "topic": topic,
            "slug": slug,
            "status": "queued",
            "progress": 5,
            "stage": "queued",
            "message": "Queued. Your research crew is getting ready.",
            "settings": {},
            "stages": self._build_stage_snapshot("queued", "running", now),
            "created_at": now,
            "updated_at": now,
            "markdown_path": None,
            "docx_path": None,
            "error": None,
        }
        self._connect().insert_one(job)
        return job

    def get_job(self, job_id):
        return self._connect().find_one({"_id": job_id})

    def list_jobs(self, limit=50):
        # Failed jobs stay in MongoDB (with their error) but are hidden from Recent notes.
        cursor = (
            self._connect()
            .find({"status": {"$ne": "failed"}}, {"topic": 1, "status": 1, "created_at": 1})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)

    def update_stage(self, job_id, stage, stage_status, progress, message, overall_status="running", **fields):
        collection = self._connect()
        job = collection.find_one({"_id": job_id})
        if not job:
            raise JobStoreError(f"Job not found: {job_id}")

        now = datetime.utcnow()
        stages = self._merge_stage(job.get("stages", []), stage, stage_status, now, message)
        update = {
            "stage": stage,
            "status": overall_status,
            "progress": progress,
            "message": message,
            "stages": stages,
            "updated_at": now,
        }
        update.update(fields)
        collection.update_one({"_id": job_id}, {"$set": update})
        return collection.find_one({"_id": job_id})

    def update_job(self, job_id, **fields):
        collection = self._connect()
        collection.update_one({"_id": job_id}, {"$set": fields})
        return collection.find_one({"_id": job_id})

    def delete_job(self, job_id):
        collection = self._connect()
        job = collection.find_one({"_id": job_id})
        if job:
            collection.delete_one({"_id": job_id})
        return job

    def mark_failed(self, job_id, stage, message, error):
        return self.update_stage(
            job_id,
            stage=stage,
            stage_status="failed",
            progress=0,
            message=message,
            overall_status="failed",
            error=error,
        )

    def _build_stage_snapshot(self, current_stage, current_status, now):
        stages = []
        for name, label in DEFAULT_STAGE_DEFS:
            status = "pending"
            started_at = None
            ended_at = None
            if name == current_stage:
                status = current_status
                started_at = now
                if current_status in {"done", "failed"}:
                    ended_at = now

            stages.append(
                {
                    "name": name,
                    "label": label,
                    "status": status,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "message": None,
                }
            )
        return stages

    def _merge_stage(self, stages, current_stage, current_status, now, message):
        known = {stage["name"]: dict(stage) for stage in stages}
        current_index = next(
            (index for index, stage in enumerate(DEFAULT_STAGE_DEFS) if stage[0] == current_stage),
            0,
        )

        merged = []
        for index, (name, label) in enumerate(DEFAULT_STAGE_DEFS):
            stage = known.get(
                name,
                {
                    "name": name,
                    "label": label,
                    "status": "pending",
                    "started_at": None,
                    "ended_at": None,
                    "message": None,
                },
            )
            stage["label"] = label

            if index < current_index and stage.get("status") not in {"done", "failed"}:
                stage["status"] = "done"
                stage["ended_at"] = stage.get("ended_at") or now
            elif index == current_index:
                stage["status"] = current_status
                stage["started_at"] = stage.get("started_at") or now
                stage["message"] = message
                if current_status in {"done", "failed"}:
                    stage["ended_at"] = now
            elif index > current_index and stage.get("status") != "failed":
                stage["status"] = "pending"

            merged.append(stage)
        return merged

    # --- Sticky notes (the user's own quick notes, stored in MongoDB) ---

    def list_stickies(self, note_id):
        cursor = (
            self._stickies_collection()
            .find({"note_id": note_id})
            .sort("updated_at", DESCENDING)
        )
        return list(cursor)

    def create_sticky(self, text, color, note_id):
        now = datetime.utcnow()
        sticky = {
            "_id": uuid.uuid4().hex,
            "note_id": note_id,
            "text": text,
            "color": color,
            "created_at": now,
            "updated_at": now,
        }
        self._stickies_collection().insert_one(sticky)
        return sticky

    def delete_stickies_for_note(self, note_id):
        self._stickies_collection().delete_many({"note_id": note_id})

    def update_sticky(self, sticky_id, text=None, color=None):
        update = {"updated_at": datetime.utcnow()}
        if text is not None:
            update["text"] = text
        if color is not None:
            update["color"] = color

        collection = self._stickies_collection()
        result = collection.update_one({"_id": sticky_id}, {"$set": update})
        if result.matched_count == 0:
            return None
        return collection.find_one({"_id": sticky_id})

    def delete_sticky(self, sticky_id):
        result = self._stickies_collection().delete_one({"_id": sticky_id})
        return result.deleted_count > 0


job_store = MongoJobStore()
