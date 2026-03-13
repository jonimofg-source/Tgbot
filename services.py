from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Profile:
    user_id: int
    name: str
    age: int
    gender: str
    looking_for: str
    city: str
    bio: str


@dataclass
class LikeRecord:
    from_user: int
    to_user: int


class ProfileRepository:
    DATA_FILE = "profiles.json"

    def __init__(self) -> None:
        self._profiles: dict[int, Profile] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.DATA_FILE):
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                p = Profile(**item)
                self._profiles[p.user_id] = p

    def _save(self) -> None:
        with open(self.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([asdict(p) for p in self._profiles.values()], f, ensure_ascii=False, indent=2)

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


class LikeRepository:
    DATA_FILE = "likes.json"

    def __init__(self) -> None:
        self._likes: list[LikeRecord] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.DATA_FILE):
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                self._likes.append(LikeRecord(**item))

    def _save(self) -> None:
        with open(self.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([{"from_user": lr.from_user, "to_user": lr.to_user} for lr in self._likes], f, ensure_ascii=False, indent=2)

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


class SkipRepository:
    DATA_FILE = "skips.json"

    def __init__(self) -> None:
        self._skips: dict[int, set[int]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.DATA_FILE):
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for uid_str, skipped in data.items():
                self._skips[int(uid_str)] = set(skipped)

    def _save(self) -> None:
        with open(self.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): list(v) for k, v in self._skips.items()}, f, ensure_ascii=False, indent=2)

    def add_skip(self, user_id: int, skipped_id: int) -> None:
        self._skips.setdefault(user_id, set()).add(skipped_id)
        self._save()

    def get_skipped(self, user_id: int) -> set[int]:
        return self._skips.get(user_id, set())

    def remove_user_skips(self, user_id: int) -> None:
        self._skips.pop(user_id, None)
        self._skips = {k: v - {user_id} for k, v in self._skips.items()}
        self._save()


class ProfileService:
    def __init__(self, repo: ProfileRepository) -> None:
        self._repo = repo

    def get_profile(self, user_id: int) -> Optional[Profile]:
        return self._repo.get(user_id)

    def has_profile(self, user_id: int) -> bool:
        return self._repo.exists(user_id)

    def create_profile(self, user_id: int, name: str, age: int, gender: str,
                        looking_for: str, city: str, bio: str) -> Profile:
        profile = Profile(
            user_id=user_id, name=name, age=age, gender=gender,
            looking_for=looking_for, city=city, bio=bio,
        )
        return self._repo.create(profile)

    def update_profile(self, user_id: int, **kwargs: str | int) -> Optional[Profile]:
        profile = self._repo.get(user_id)
        if profile is None:
            return None
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        return self._repo.update(profile)

    def delete_profile(self, user_id: int) -> bool:
        return self._repo.delete(user_id)

    def format_profile(self, profile: Profile) -> str:
        gender_label = "Male" if profile.gender == "male" else "Female"
        looking_label = "Male" if profile.looking_for == "male" else ("Female" if profile.looking_for == "female" else "Any")
        return (
            f"Name: {profile.name}\n"
            f"Age: {profile.age}\n"
            f"Gender: {gender_label}\n"
            f"Looking for: {looking_label}\n"
            f"City: {profile.city}\n"
            f"Bio: {profile.bio}"
        )


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
            if user_profile.looking_for != "any" and profile.gender != user_profile.looking_for:
                continue
            yield_profile = True
            if yield_profile:
                return profile
        return None

    def cleanup_user(self, user_id: int) -> None:
        self._like_repo.remove_user_likes(user_id)
        self._skip_repo.remove_user_skips(user_id)


profile_repo = ProfileRepository()
like_repo = LikeRepository()
skip_repo = SkipRepository()

profile_service = ProfileService(profile_repo)
match_service = MatchService(profile_repo, like_repo, skip_repo)
