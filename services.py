from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, asdict, field
from typing import Optional

logger = logging.getLogger(__name__)

# --- Admin config ---
ADMIN_IDS: set[int] = set()

_admin_file = os.environ.get("ADMIN_FILE", "admins.json")
if os.path.exists(_admin_file):
    try:
        with open(_admin_file, "r", encoding="utf-8") as _f:
            ADMIN_IDS = set(json.load(_f))
    except (json.JSONDecodeError, OSError):
        pass


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# --- JSON helpers ---

def _safe_load_json(path: str, default: object = None) -> object:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.error("Повреждён файл %s: %s. Используется значение по умолчанию.", path, e)
        backup = path + ".corrupted"
        try:
            os.replace(path, backup)
            logger.info("Повреждённый файл сохранён как %s", backup)
        except OSError:
            pass
        return default


def _atomic_save_json(path: str, data: object) -> None:
    dir_name = os.path.dirname(path) or "."
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as e:
        logger.error("Ошибка записи %s: %s", path, e)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# --- Data models ---

@dataclass
class Profile:
    user_id: int
    name: str
    age: int
    gender: str
    looking_for: str
    city: str
    bio: str
    photo_id: Optional[str] = None
    banned: bool = False


@dataclass
class LikeRecord:
    from_user: int
    to_user: int


@dataclass
class Report:
    id: int
    from_user: int
    reported_user: int
    reason: str
    timestamp: float = 0.0
    resolved: bool = False
    resolution: str = ""


@dataclass
class ChatSession:
    user_a: int
    user_b: int
    a_accepted: bool = False
    b_accepted: bool = False

    @property
    def both_accepted(self) -> bool:
        return self.a_accepted and self.b_accepted

    def is_participant(self, user_id: int) -> bool:
        return user_id in (self.user_a, self.user_b)

    def partner_of(self, user_id: int) -> Optional[int]:
        if user_id == self.user_a:
            return self.user_b
        if user_id == self.user_b:
            return self.user_a
        return None


# --- Repositories ---

class ProfileRepository:
    DATA_FILE = "profiles.json"

    def __init__(self) -> None:
        self._profiles: dict[int, Profile] = {}
        self._load()

    def _load(self) -> None:
        data = _safe_load_json(self.DATA_FILE, default=[])
        if isinstance(data, list):
            for item in data:
                try:
                    item.setdefault("photo_id", None)
                    item.setdefault("banned", False)
                    p = Profile(**item)
                    self._profiles[p.user_id] = p
                except (TypeError, KeyError) as e:
                    logger.warning("Пропущена некорректная анкета: %s", e)

    def _save(self) -> None:
        _atomic_save_json(self.DATA_FILE, [asdict(p) for p in self._profiles.values()])

    def get(self, user_id: int) -> Optional[Profile]:
        return self._profiles.get(user_id)

    def exists(self, user_id: int) -> bool:
        return user_id in self._profiles

    def create(self, profile: Profile) -> Profile:
        self._profiles[profile.user_id] = profile
        self._save()
        return profile

    def update(self, profile: Profile) -> Profile:
        self._profiles[profile.user_id] = profile
        self._save()
        return profile

    def delete(self, user_id: int) -> bool:
        if user_id in self._profiles:
            del self._profiles[user_id]
            self._save()
            return True
        return False

    def all_profiles(self) -> list[Profile]:
        return list(self._profiles.values())

    def count(self) -> int:
        return len(self._profiles)


class LikeRepository:
    DATA_FILE = "likes.json"

    def __init__(self) -> None:
        self._likes: list[LikeRecord] = []
        self._load()

    def _load(self) -> None:
        data = _safe_load_json(self.DATA_FILE, default=[])
        if isinstance(data, list):
            for item in data:
                try:
                    self._likes.append(LikeRecord(**item))
                except (TypeError, KeyError) as e:
                    logger.warning("Пропущена некорректная запись лайка: %s", e)

    def _save(self) -> None:
        _atomic_save_json(
            self.DATA_FILE,
            [{"from_user": lr.from_user, "to_user": lr.to_user} for lr in self._likes],
        )

    def add_like(self, from_user: int, to_user: int) -> None:
        if not self.has_like(from_user, to_user):
            self._likes.append(LikeRecord(from_user=from_user, to_user=to_user))
            self._save()

    def has_like(self, from_user: int, to_user: int) -> bool:
        return any(lr.from_user == from_user and lr.to_user == to_user for lr in self._likes)

    def is_match(self, user_a: int, user_b: int) -> bool:
        return self.has_like(user_a, user_b) and self.has_like(user_b, user_a)

    def get_liked_by(self, user_id: int) -> list[int]:
        return [lr.to_user for lr in self._likes if lr.from_user == user_id]

    def get_who_liked(self, user_id: int) -> list[int]:
        return [lr.from_user for lr in self._likes if lr.to_user == user_id]

    def remove_user_likes(self, user_id: int) -> None:
        self._likes = [lr for lr in self._likes if lr.from_user != user_id and lr.to_user != user_id]
        self._save()

    def count(self) -> int:
        return len(self._likes)


class SkipRepository:
    DATA_FILE = "skips.json"

    def __init__(self) -> None:
        self._skips: dict[int, set[int]] = {}
        self._load()

    def _load(self) -> None:
        data = _safe_load_json(self.DATA_FILE, default={})
        if isinstance(data, dict):
            for uid_str, skipped in data.items():
                try:
                    self._skips[int(uid_str)] = set(skipped)
                except (ValueError, TypeError) as e:
                    logger.warning("Пропущена некорректная запись пропуска: %s", e)

    def _save(self) -> None:
        _atomic_save_json(
            self.DATA_FILE,
            {str(k): list(v) for k, v in self._skips.items()},
        )

    def add_skip(self, user_id: int, skipped_id: int) -> None:
        self._skips.setdefault(user_id, set()).add(skipped_id)
        self._save()

    def get_skipped(self, user_id: int) -> set[int]:
        return set(self._skips.get(user_id, set()))

    def remove_user_skips(self, user_id: int) -> None:
        self._skips.pop(user_id, None)
        self._skips = {k: v - {user_id} for k, v in self._skips.items()}
        self._save()


class ReportRepository:
    DATA_FILE = "reports.json"

    def __init__(self) -> None:
        self._reports: list[Report] = []
        self._next_id: int = 1
        self._load()

    def _load(self) -> None:
        data = _safe_load_json(self.DATA_FILE, default=[])
        if isinstance(data, list):
            for item in data:
                try:
                    item.setdefault("timestamp", 0.0)
                    item.setdefault("resolved", False)
                    item.setdefault("resolution", "")
                    self._reports.append(Report(**item))
                except (TypeError, KeyError) as e:
                    logger.warning("Пропущена некорректная жалоба: %s", e)
            if self._reports:
                self._next_id = max(r.id for r in self._reports) + 1

    def _save(self) -> None:
        _atomic_save_json(self.DATA_FILE, [asdict(r) for r in self._reports])

    def add(self, from_user: int, reported_user: int, reason: str) -> Report:
        report = Report(
            id=self._next_id,
            from_user=from_user,
            reported_user=reported_user,
            reason=reason,
            timestamp=time.time(),
        )
        self._next_id += 1
        self._reports.append(report)
        self._save()
        return report

    def get_unresolved(self) -> list[Report]:
        return [r for r in self._reports if not r.resolved]

    def get_by_id(self, report_id: int) -> Optional[Report]:
        for r in self._reports:
            if r.id == report_id:
                return r
        return None

    def resolve(self, report_id: int, resolution: str) -> Optional[Report]:
        report = self.get_by_id(report_id)
        if report is None:
            return None
        report.resolved = True
        report.resolution = resolution
        self._save()
        return report

    def count_for_user(self, user_id: int) -> int:
        return sum(1 for r in self._reports if r.reported_user == user_id)

    def count_unresolved(self) -> int:
        return len(self.get_unresolved())

    def remove_user_reports(self, user_id: int) -> None:
        self._reports = [r for r in self._reports if r.from_user != user_id and r.reported_user != user_id]
        self._save()


class ChatRepository:
    """In-memory chat sessions (no persistence needed — chats are ephemeral)."""

    def __init__(self) -> None:
        self._sessions: dict[int, ChatSession] = {}
        self._user_to_session: dict[int, int] = {}
        self._next_id: int = 1

    def create(self, user_a: int, user_b: int) -> ChatSession:
        self.remove_user(user_a)
        self.remove_user(user_b)
        session = ChatSession(user_a=user_a, user_b=user_b)
        sid = self._next_id
        self._next_id += 1
        self._sessions[sid] = session
        self._user_to_session[user_a] = sid
        self._user_to_session[user_b] = sid
        return session

    def get_by_user(self, user_id: int) -> Optional[ChatSession]:
        sid = self._user_to_session.get(user_id)
        if sid is None:
            return None
        return self._sessions.get(sid)

    def accept(self, user_id: int) -> Optional[ChatSession]:
        session = self.get_by_user(user_id)
        if session is None:
            return None
        if user_id == session.user_a:
            session.a_accepted = True
        elif user_id == session.user_b:
            session.b_accepted = True
        return session

    def remove_user(self, user_id: int) -> Optional[ChatSession]:
        sid = self._user_to_session.pop(user_id, None)
        if sid is None:
            return None
        session = self._sessions.get(sid)
        if session is None:
            return None
        partner = session.partner_of(user_id)
        if partner is not None:
            self._user_to_session.pop(partner, None)
        self._sessions.pop(sid, None)
        return session

    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.both_accepted)


# --- Services ---

class ProfileService:
    def __init__(self, repo: ProfileRepository) -> None:
        self._repo = repo

    def get_profile(self, user_id: int) -> Optional[Profile]:
        return self._repo.get(user_id)

    def has_profile(self, user_id: int) -> bool:
        return self._repo.exists(user_id)

    def is_banned(self, user_id: int) -> bool:
        p = self._repo.get(user_id)
        return p is not None and p.banned

    def create_profile(self, user_id: int, name: str, age: int, gender: str,
                        looking_for: str, city: str, bio: str,
                        photo_id: Optional[str] = None) -> Profile:
        profile = Profile(
            user_id=user_id, name=name, age=age, gender=gender,
            looking_for=looking_for, city=city, bio=bio,
            photo_id=photo_id,
        )
        return self._repo.create(profile)

    def update_profile(self, user_id: int, **kwargs) -> Optional[Profile]:
        profile = self._repo.get(user_id)
        if profile is None:
            return None
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        return self._repo.update(profile)

    def ban_user(self, user_id: int) -> bool:
        profile = self._repo.get(user_id)
        if profile is None:
            return False
        profile.banned = True
        self._repo.update(profile)
        return True

    def unban_user(self, user_id: int) -> bool:
        profile = self._repo.get(user_id)
        if profile is None:
            return False
        profile.banned = False
        self._repo.update(profile)
        return True

    def delete_profile(self, user_id: int) -> bool:
        return self._repo.delete(user_id)

    def format_profile(self, profile: Profile) -> str:
        gender_label = "👨 Парень" if profile.gender == "male" else "👩 Девушка"
        looking_map = {"male": "👨 Парней", "female": "👩 Девушек", "any": "💫 Всех"}
        looking_label = looking_map.get(profile.looking_for, "💫 Всех")
        return (
            f"👤 Имя: {profile.name}\n"
            f"🎂 Возраст: {profile.age}\n"
            f"⚧ Пол: {gender_label}\n"
            f"🔍 Ищу: {looking_label}\n"
            f"🏙 Город: {profile.city}\n"
            f"📝 О себе: {profile.bio}"
        )

    def stats(self) -> dict:
        profiles = self._repo.all_profiles()
        total = len(profiles)
        banned = sum(1 for p in profiles if p.banned)
        with_photo = sum(1 for p in profiles if p.photo_id)
        return {"total": total, "banned": banned, "with_photo": with_photo}


class MatchService:
    def __init__(self, profile_repo: ProfileRepository, like_repo: LikeRepository,
                 skip_repo: SkipRepository) -> None:
        self._profile_repo = profile_repo
        self._like_repo = like_repo
        self._skip_repo = skip_repo

    def like(self, from_user: int, to_user: int) -> bool:
        self._like_repo.add_like(from_user, to_user)
        return self._like_repo.is_match(from_user, to_user)

    def skip(self, from_user: int, to_user: int) -> None:
        self._skip_repo.add_skip(from_user, to_user)

    def get_next_profile(self, user_id: int) -> Optional[Profile]:
        user_profile = self._profile_repo.get(user_id)
        if user_profile is None:
            return None

        liked_ids = set(self._like_repo.get_liked_by(user_id))
        skipped_ids = self._skip_repo.get_skipped(user_id)
        excluded = liked_ids | skipped_ids | {user_id}

        for profile in self._profile_repo.all_profiles():
            if profile.user_id in excluded:
                continue
            if profile.banned:
                continue
            if user_profile.looking_for != "any" and profile.gender != user_profile.looking_for:
                continue
            return profile
        return None

    def cleanup_user(self, user_id: int) -> None:
        self._like_repo.remove_user_likes(user_id)
        self._skip_repo.remove_user_skips(user_id)

    def stats(self) -> dict:
        return {"total_likes": self._like_repo.count()}


class ReportService:
    def __init__(self, repo: ReportRepository) -> None:
        self._repo = repo

    def file_report(self, from_user: int, reported_user: int, reason: str) -> Report:
        return self._repo.add(from_user, reported_user, reason)

    def get_unresolved(self) -> list[Report]:
        return self._repo.get_unresolved()

    def resolve(self, report_id: int, resolution: str) -> Optional[Report]:
        return self._repo.resolve(report_id, resolution)

    def count_for_user(self, user_id: int) -> int:
        return self._repo.count_for_user(user_id)

    def count_unresolved(self) -> int:
        return self._repo.count_unresolved()

    def cleanup_user(self, user_id: int) -> None:
        self._repo.remove_user_reports(user_id)


class ChatService:
    def __init__(self, repo: ChatRepository) -> None:
        self._repo = repo

    def create_chat(self, user_a: int, user_b: int) -> ChatSession:
        return self._repo.create(user_a, user_b)

    def get_session(self, user_id: int) -> Optional[ChatSession]:
        return self._repo.get_by_user(user_id)

    def accept(self, user_id: int) -> Optional[ChatSession]:
        return self._repo.accept(user_id)

    def end_chat(self, user_id: int) -> Optional[ChatSession]:
        return self._repo.remove_user(user_id)

    def get_partner(self, user_id: int) -> Optional[int]:
        session = self._repo.get_by_user(user_id)
        if session is None or not session.both_accepted:
            return None
        return session.partner_of(user_id)

    def stats(self) -> dict:
        return {"active_chats": self._repo.active_count()}


# --- Singletons ---

profile_repo = ProfileRepository()
like_repo = LikeRepository()
skip_repo = SkipRepository()
report_repo = ReportRepository()
chat_repo = ChatRepository()

profile_service = ProfileService(profile_repo)
match_service = MatchService(profile_repo, like_repo, skip_repo)
report_service = ReportService(report_repo)
chat_service = ChatService(chat_repo)
