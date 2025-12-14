import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler


class FileManager:
    def __init__(self, upload_dir: str = "./uploads", expiry_hours: int = 24):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_hours = expiry_hours
        self.metadata_file = self.upload_dir / ".metadata.json"
        self.metadata: Dict[str, Dict[str, Any]] = self._load_metadata()
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self.cleanup_expired_files, 'interval', hours=1, id='cleanup_job')

    def start_scheduler(self):
        if not self.scheduler.running:
            self.scheduler.start()
            print(" File cleanup scheduler started (runs every hour)")

    def stop_scheduler(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_metadata(self):
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)

    def add_file(self, source_path: Path, original_filename: str,
                 video_title: str = "", video_id: str = "") -> Optional[str]:
        if not source_path.exists():
            return None

        file_uuid = str(uuid.uuid4())
        new_filename = f"{file_uuid}{source_path.suffix}"
        dest_path = self.upload_dir / new_filename

        shutil.move(str(source_path), str(dest_path))

        now = datetime.now()
        self.metadata[file_uuid] = {
            "original_filename": original_filename,
            "video_title": video_title,
            "video_id": video_id,
            "extension": source_path.suffix,
            "filename": new_filename,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=self.expiry_hours)).isoformat(),
            "size_bytes": dest_path.stat().st_size
        }
        self._save_metadata()
        return file_uuid

    def get_file_info(self, file_uuid: str) -> Optional[Dict[str, Any]]:
        return self.metadata.get(file_uuid)

    def get_file_path(self, file_uuid: str) -> Optional[Path]:
        info = self.get_file_info(file_uuid)
        if info:
            path = self.upload_dir / info["filename"]
            if path.exists():
                return path
        return None

    def delete_file(self, file_uuid: str) -> bool:
        info = self.metadata.get(file_uuid)
        if not info:
            return False

        file_path = self.upload_dir / info["filename"]
        if file_path.exists():
            file_path.unlink()

        del self.metadata[file_uuid]
        self._save_metadata()
        return True

    def cleanup_expired_files(self):
        now = datetime.now()
        expired = [
            uid for uid, info in self.metadata.items()
            if now > datetime.fromisoformat(info["expires_at"])
        ]

        for file_uuid in expired:
            info = self.metadata[file_uuid]
            file_path = self.upload_dir / info["filename"]
            if file_path.exists():
                file_path.unlink()
                print(f" Deleted expired: {info['video_title']} ({file_uuid})")
            del self.metadata[file_uuid]

        if expired:
            self._save_metadata()
            print(f" Cleaned up {len(expired)} expired file(s)")

    def get_stats(self) -> Dict[str, Any]:
        total_size = sum(info.get("size_bytes", 0) for info in self.metadata.values())
        return {
            "total_files": len(self.metadata),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "expiry_hours": self.expiry_hours
        }