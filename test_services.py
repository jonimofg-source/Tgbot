import os
import json
import unittest

os.environ.setdefault("TESTING", "1")

from services import (
    Profile, ProfileRepository, LikeRepository, SkipRepository,
    ProfileService, MatchService, ReportRepository, ReportService,
    ChatRepository, ChatService,
    UnbanRequestRepository, UnbanRequestService,
    _safe_load_json, _atomic_save_json,
)


class TestProfileRepository(unittest.TestCase):
    DATA_FILE = "test_profiles.json"

    def setUp(self):
        self.repo = ProfileRepository()
        self.repo.DATA_FILE = self.DATA_FILE
        self.repo._profiles = {}

    def tearDown(self):
        if os.path.exists(self.DATA_FILE):
            os.unlink(self.DATA_FILE)

    def _make_profile(self, uid=1, photo_id=None, banned=False, paused=False):
        return Profile(uid, "Тест", 25, "male", "female", "Москва", "Привет",
                       photo_id=photo_id, banned=banned, paused=paused)

    def test_create_and_get(self):
        p = self._make_profile()
        self.repo.create(p)
        result = self.repo.get(1)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Тест")

    def test_exists(self):
        self.assertFalse(self.repo.exists(1))
        self.repo.create(self._make_profile())
        self.assertTrue(self.repo.exists(1))

    def test_update(self):
        p = self._make_profile()
        self.repo.create(p)
        p.name = "Новое имя"
        self.repo.update(p)
        self.assertEqual(self.repo.get(1).name, "Новое имя")

    def test_delete(self):
        self.repo.create(self._make_profile())
        self.assertTrue(self.repo.delete(1))
        self.assertFalse(self.repo.exists(1))
        self.assertFalse(self.repo.delete(1))

    def test_all_profiles(self):
        self.repo.create(self._make_profile(1))
        self.repo.create(self._make_profile(2))
        self.assertEqual(len(self.repo.all_profiles()), 2)

    def test_persistence(self):
        self.repo.create(self._make_profile())
        repo2 = ProfileRepository()
        repo2.DATA_FILE = self.DATA_FILE
        repo2._profiles = {}
        repo2._load()
        self.assertTrue(repo2.exists(1))

    def test_photo_id_stored(self):
        p = self._make_profile(photo_id="abc123")
        self.repo.create(p)
        self.assertEqual(self.repo.get(1).photo_id, "abc123")

    def test_banned_stored(self):
        p = self._make_profile(banned=True)
        self.repo.create(p)
        self.assertTrue(self.repo.get(1).banned)

    def test_count(self):
        self.assertEqual(self.repo.count(), 0)
        self.repo.create(self._make_profile(1))
        self.repo.create(self._make_profile(2))
        self.assertEqual(self.repo.count(), 2)

    def test_paused_stored(self):
        p = self._make_profile(paused=True)
        self.repo.create(p)
        self.assertTrue(self.repo.get(1).paused)

    def test_backward_compat_load(self):
        """Old profiles without photo_id/banned should load fine."""
        data = [{"user_id": 1, "name": "Old", "age": 20, "gender": "male",
                 "looking_for": "female", "city": "X", "bio": "Y"}]
        with open(self.DATA_FILE, "w") as f:
            json.dump(data, f)
        repo = ProfileRepository()
        repo.DATA_FILE = self.DATA_FILE
        repo._profiles = {}
        repo._load()
        p = repo.get(1)
        self.assertIsNotNone(p)
        self.assertIsNone(p.photo_id)
        self.assertFalse(p.banned)
        self.assertFalse(p.paused)


class TestLikeRepository(unittest.TestCase):
    DATA_FILE = "test_likes.json"

    def setUp(self):
        self.repo = LikeRepository()
        self.repo.DATA_FILE = self.DATA_FILE
        self.repo._likes = []

    def tearDown(self):
        if os.path.exists(self.DATA_FILE):
            os.unlink(self.DATA_FILE)

    def test_add_and_has_like(self):
        self.assertFalse(self.repo.has_like(1, 2))
        self.repo.add_like(1, 2)
        self.assertTrue(self.repo.has_like(1, 2))
        self.assertFalse(self.repo.has_like(2, 1))

    def test_no_duplicate_likes(self):
        self.repo.add_like(1, 2)
        self.repo.add_like(1, 2)
        self.assertEqual(len(self.repo._likes), 1)

    def test_is_match(self):
        self.repo.add_like(1, 2)
        self.assertFalse(self.repo.is_match(1, 2))
        self.repo.add_like(2, 1)
        self.assertTrue(self.repo.is_match(1, 2))
        self.assertTrue(self.repo.is_match(2, 1))

    def test_get_liked_by(self):
        self.repo.add_like(1, 2)
        self.repo.add_like(1, 3)
        self.assertEqual(self.repo.get_liked_by(1), [2, 3])

    def test_get_who_liked(self):
        self.repo.add_like(2, 1)
        self.repo.add_like(3, 1)
        self.assertEqual(self.repo.get_who_liked(1), [2, 3])

    def test_remove_user_likes(self):
        self.repo.add_like(1, 2)
        self.repo.add_like(2, 1)
        self.repo.add_like(3, 1)
        self.repo.remove_user_likes(1)
        self.assertFalse(self.repo.has_like(1, 2))
        self.assertFalse(self.repo.has_like(2, 1))
        self.assertFalse(self.repo.has_like(3, 1))

    def test_count(self):
        self.assertEqual(self.repo.count(), 0)
        self.repo.add_like(1, 2)
        self.repo.add_like(2, 3)
        self.assertEqual(self.repo.count(), 2)


class TestSkipRepository(unittest.TestCase):
    DATA_FILE = "test_skips.json"

    def setUp(self):
        self.repo = SkipRepository()
        self.repo.DATA_FILE = self.DATA_FILE
        self.repo._skips = {}

    def tearDown(self):
        if os.path.exists(self.DATA_FILE):
            os.unlink(self.DATA_FILE)

    def test_add_and_get_skipped(self):
        self.assertEqual(self.repo.get_skipped(1), set())
        self.repo.add_skip(1, 2)
        self.repo.add_skip(1, 3)
        self.assertEqual(self.repo.get_skipped(1), {2, 3})

    def test_get_skipped_returns_copy(self):
        self.repo.add_skip(1, 2)
        skipped = self.repo.get_skipped(1)
        skipped.add(999)
        self.assertNotIn(999, self.repo.get_skipped(1))

    def test_remove_user_skips(self):
        self.repo.add_skip(1, 2)
        self.repo.add_skip(2, 3)
        self.repo.add_skip(3, 1)
        self.repo.remove_user_skips(1)
        self.assertEqual(self.repo.get_skipped(1), set())
        self.assertNotIn(1, self.repo.get_skipped(3))


class TestReportRepository(unittest.TestCase):
    DATA_FILE = "test_reports.json"

    def setUp(self):
        self.repo = ReportRepository()
        self.repo.DATA_FILE = self.DATA_FILE
        self.repo._reports = []
        self.repo._next_id = 1

    def tearDown(self):
        if os.path.exists(self.DATA_FILE):
            os.unlink(self.DATA_FILE)

    def test_add_report(self):
        r = self.repo.add(100, 200, "Спам")
        self.assertEqual(r.id, 1)
        self.assertEqual(r.from_user, 100)
        self.assertEqual(r.reported_user, 200)
        self.assertEqual(r.reason, "Спам")
        self.assertFalse(r.resolved)
        self.assertIsNone(r.photo_id)

    def test_add_report_with_photo(self):
        r = self.repo.add(100, 200, "Спам", photo_id="photo123")
        self.assertEqual(r.photo_id, "photo123")

    def test_get_unresolved(self):
        self.repo.add(100, 200, "Спам")
        self.repo.add(101, 201, "Оскорбление")
        self.assertEqual(len(self.repo.get_unresolved()), 2)

    def test_resolve(self):
        r = self.repo.add(100, 200, "Спам")
        resolved = self.repo.resolve(r.id, "dismissed")
        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.resolution, "dismissed")
        self.assertEqual(len(self.repo.get_unresolved()), 0)

    def test_resolve_nonexistent(self):
        result = self.repo.resolve(999, "dismissed")
        self.assertIsNone(result)

    def test_resolve_already_resolved(self):
        r = self.repo.add(100, 200, "Спам")
        self.repo.resolve(r.id, "dismissed")
        result = self.repo.resolve(r.id, "banned")
        self.assertIsNone(result)

    def test_count_for_user(self):
        self.repo.add(100, 200, "Спам")
        self.repo.add(101, 200, "Фейк")
        self.repo.add(102, 300, "Бот")
        self.assertEqual(self.repo.count_for_user(200), 2)
        self.assertEqual(self.repo.count_for_user(300), 1)

    def test_count_unresolved(self):
        self.repo.add(100, 200, "Спам")
        r = self.repo.add(101, 201, "Фейк")
        self.assertEqual(self.repo.count_unresolved(), 2)
        self.repo.resolve(r.id, "dismissed")
        self.assertEqual(self.repo.count_unresolved(), 1)

    def test_remove_user_reports(self):
        self.repo.add(100, 200, "Спам")
        self.repo.add(200, 300, "Фейк")
        self.repo.remove_user_reports(200)
        self.assertEqual(len(self.repo._reports), 0)

    def test_auto_increment_ids(self):
        r1 = self.repo.add(100, 200, "A")
        r2 = self.repo.add(100, 201, "B")
        self.assertEqual(r1.id, 1)
        self.assertEqual(r2.id, 2)


class TestChatRepository(unittest.TestCase):
    def setUp(self):
        self.repo = ChatRepository()

    def test_create_and_get(self):
        session = self.repo.create(1, 2)
        self.assertIsNotNone(session)
        self.assertEqual(session.user_a, 1)
        self.assertEqual(session.user_b, 2)
        self.assertFalse(session.a_accepted)
        self.assertFalse(session.b_accepted)

    def test_get_by_user(self):
        self.repo.create(1, 2)
        s1 = self.repo.get_by_user(1)
        s2 = self.repo.get_by_user(2)
        self.assertIsNotNone(s1)
        self.assertIsNotNone(s2)
        self.assertIs(s1, s2)

    def test_accept(self):
        self.repo.create(1, 2)
        s = self.repo.accept(1)
        self.assertTrue(s.a_accepted)
        self.assertFalse(s.b_accepted)
        self.assertFalse(s.both_accepted)

        self.repo.accept(2)
        self.assertTrue(s.both_accepted)

    def test_partner_of(self):
        session = self.repo.create(1, 2)
        self.assertEqual(session.partner_of(1), 2)
        self.assertEqual(session.partner_of(2), 1)
        self.assertIsNone(session.partner_of(3))

    def test_remove_user(self):
        self.repo.create(1, 2)
        session = self.repo.remove_user(1)
        self.assertIsNotNone(session)
        self.assertIsNone(self.repo.get_by_user(1))
        self.assertIsNone(self.repo.get_by_user(2))

    def test_create_overwrites_existing(self):
        self.repo.create(1, 2)
        self.repo.create(1, 3)
        s = self.repo.get_by_user(1)
        self.assertEqual(s.user_b, 3)
        self.assertIsNone(self.repo.get_by_user(2))

    def test_active_count(self):
        self.assertEqual(self.repo.active_count(), 0)
        self.repo.create(1, 2)
        self.repo.accept(1)
        self.repo.accept(2)
        self.assertEqual(self.repo.active_count(), 1)

    def test_nonexistent_user(self):
        self.assertIsNone(self.repo.get_by_user(999))
        self.assertIsNone(self.repo.accept(999))
        self.assertIsNone(self.repo.remove_user(999))


class TestProfileService(unittest.TestCase):
    def setUp(self):
        self.repo = ProfileRepository()
        self.repo._profiles = {}
        self.service = ProfileService(self.repo)

    def test_create_with_photo(self):
        p = self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе", photo_id="abc")
        self.assertEqual(p.photo_id, "abc")

    def test_create_without_photo(self):
        p = self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе")
        self.assertIsNone(p.photo_id)

    def test_has_profile(self):
        self.assertFalse(self.service.has_profile(1))
        self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе")
        self.assertTrue(self.service.has_profile(1))

    def test_update_profile(self):
        self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе")
        updated = self.service.update_profile(1, name="Аня", age=23)
        self.assertEqual(updated.name, "Аня")
        self.assertEqual(updated.age, 23)

    def test_update_photo(self):
        self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе")
        updated = self.service.update_profile(1, photo_id="new_photo")
        self.assertEqual(updated.photo_id, "new_photo")

    def test_update_nonexistent(self):
        result = self.service.update_profile(999, name="Тест")
        self.assertIsNone(result)

    def test_ban_and_unban(self):
        self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе")
        self.assertFalse(self.service.is_banned(1))
        self.assertTrue(self.service.ban_user(1))
        self.assertTrue(self.service.is_banned(1))
        self.assertTrue(self.service.unban_user(1))
        self.assertFalse(self.service.is_banned(1))

    def test_ban_nonexistent(self):
        self.assertFalse(self.service.ban_user(999))

    def test_is_banned_no_profile(self):
        self.assertFalse(self.service.is_banned(999))

    def test_delete(self):
        self.service.create_profile(1, "Анна", 22, "female", "male", "СПб", "Кофе")
        self.assertTrue(self.service.delete_profile(1))
        self.assertFalse(self.service.has_profile(1))

    def test_toggle_pause(self):
        self.service.create_profile(1, "A", 20, "male", "female", "M", "X")
        self.assertFalse(self.service.is_paused(1))
        result = self.service.toggle_pause(1)
        self.assertTrue(result)
        self.assertTrue(self.service.is_paused(1))
        result = self.service.toggle_pause(1)
        self.assertFalse(result)
        self.assertFalse(self.service.is_paused(1))

    def test_toggle_pause_nonexistent(self):
        self.assertIsNone(self.service.toggle_pause(999))

    def test_is_paused_no_profile(self):
        self.assertFalse(self.service.is_paused(999))

    def test_format_profile_male(self):
        p = Profile(1, "Иван", 25, "male", "female", "Москва", "Привет")
        text = self.service.format_profile(p)
        self.assertIn("👨 Парень", text)
        self.assertIn("👩 Девушек", text)
        self.assertIn("Иван", text)

    def test_format_profile_female_any(self):
        p = Profile(2, "Анна", 22, "female", "any", "СПб", "Кофе")
        text = self.service.format_profile(p)
        self.assertIn("👩 Девушка", text)
        self.assertIn("💫 Всех", text)

    def test_stats(self):
        self.service.create_profile(1, "A", 20, "male", "female", "M", "X", photo_id="p1")
        self.service.create_profile(2, "B", 21, "female", "male", "M", "Y")
        self.service.ban_user(2)
        stats = self.service.stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["with_photo"], 1)
        self.assertEqual(stats["banned"], 1)
        self.assertEqual(stats["paused"], 0)
        self.service.toggle_pause(1)
        stats = self.service.stats()
        self.assertEqual(stats["paused"], 1)


class TestMatchService(unittest.TestCase):
    def setUp(self):
        self.profile_repo = ProfileRepository()
        self.profile_repo._profiles = {}
        self.like_repo = LikeRepository()
        self.like_repo._likes = []
        self.skip_repo = SkipRepository()
        self.skip_repo._skips = {}
        self.service = MatchService(self.profile_repo, self.like_repo, self.skip_repo)

        self.profile_repo.create(Profile(1, "Иван", 25, "male", "female", "Москва", "Привет"))
        self.profile_repo.create(Profile(2, "Анна", 22, "female", "male", "Москва", "Кофе"))
        self.profile_repo.create(Profile(3, "Мария", 23, "female", "male", "СПб", "Бег"))
        self.profile_repo.create(Profile(4, "Пётр", 28, "male", "female", "Москва", "Спорт"))

    def test_get_next_profile_filters_by_gender(self):
        candidate = self.service.get_next_profile(1)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.gender, "female")

    def test_get_next_excludes_self(self):
        candidate = self.service.get_next_profile(1)
        self.assertNotEqual(candidate.user_id, 1)

    def test_get_next_excludes_liked(self):
        self.service.like(1, 2)
        candidate = self.service.get_next_profile(1)
        self.assertNotEqual(candidate.user_id, 2)
        self.assertEqual(candidate.user_id, 3)

    def test_get_next_excludes_skipped(self):
        self.service.skip(1, 2)
        candidate = self.service.get_next_profile(1)
        self.assertNotEqual(candidate.user_id, 2)
        self.assertEqual(candidate.user_id, 3)

    def test_get_next_excludes_banned(self):
        self.profile_repo.get(2).banned = True
        candidate = self.service.get_next_profile(1)
        self.assertEqual(candidate.user_id, 3)

    def test_get_next_excludes_paused(self):
        self.profile_repo.get(2).paused = True
        candidate = self.service.get_next_profile(1)
        self.assertEqual(candidate.user_id, 3)

    def test_get_next_returns_none_when_exhausted(self):
        self.service.like(1, 2)
        self.service.skip(1, 3)
        candidate = self.service.get_next_profile(1)
        self.assertIsNone(candidate)

    def test_mutual_like_is_match(self):
        self.assertFalse(self.service.like(1, 2))
        self.assertTrue(self.service.like(2, 1))

    def test_no_match_without_mutual(self):
        self.assertFalse(self.service.like(1, 2))
        self.assertFalse(self.service.like(1, 3))

    def test_cleanup_user(self):
        self.service.like(1, 2)
        self.service.skip(1, 3)
        self.service.cleanup_user(1)
        candidate = self.service.get_next_profile(1)
        self.assertEqual(candidate.user_id, 2)

    def test_gender_filter_any(self):
        self.profile_repo.create(Profile(5, "Саша", 26, "female", "any", "Москва", "Хобби"))
        candidate = self.service.get_next_profile(5)
        self.assertIsNotNone(candidate)

    def test_no_profile_returns_none(self):
        result = self.service.get_next_profile(999)
        self.assertIsNone(result)

    def test_stats(self):
        self.service.like(1, 2)
        self.service.like(2, 1)
        stats = self.service.stats()
        self.assertEqual(stats["total_likes"], 2)


class TestReportService(unittest.TestCase):
    def setUp(self):
        self.repo = ReportRepository()
        self.repo._reports = []
        self.repo._next_id = 1
        self.service = ReportService(self.repo)

    def test_file_report(self):
        r = self.service.file_report(100, 200, "Спам")
        self.assertEqual(r.id, 1)
        self.assertEqual(r.reason, "Спам")
        self.assertIsNone(r.photo_id)

    def test_file_report_with_photo(self):
        r = self.service.file_report(100, 200, "Спам", photo_id="img456")
        self.assertEqual(r.photo_id, "img456")

    def test_get_unresolved(self):
        self.service.file_report(100, 200, "Спам")
        self.service.file_report(101, 201, "Фейк")
        self.assertEqual(len(self.service.get_unresolved()), 2)

    def test_resolve(self):
        r = self.service.file_report(100, 200, "Спам")
        resolved = self.service.resolve(r.id, "banned")
        self.assertTrue(resolved.resolved)
        self.assertEqual(len(self.service.get_unresolved()), 0)

    def test_count_for_user(self):
        self.service.file_report(100, 200, "Спам")
        self.service.file_report(101, 200, "Фейк")
        self.assertEqual(self.service.count_for_user(200), 2)

    def test_count_unresolved(self):
        self.service.file_report(100, 200, "Спам")
        self.assertEqual(self.service.count_unresolved(), 1)

    def test_cleanup_user(self):
        self.service.file_report(100, 200, "Спам")
        self.service.file_report(200, 300, "Фейк")
        self.service.cleanup_user(200)
        self.assertEqual(self.service.count_unresolved(), 0)


class TestChatService(unittest.TestCase):
    def setUp(self):
        self.repo = ChatRepository()
        self.service = ChatService(self.repo)

    def test_create_and_get(self):
        session = self.service.create_chat(1, 2)
        self.assertIsNotNone(session)
        self.assertEqual(self.service.get_session(1), session)

    def test_accept_and_partner(self):
        self.service.create_chat(1, 2)
        self.assertIsNone(self.service.get_partner(1))

        self.service.accept(1)
        self.assertIsNone(self.service.get_partner(1))

        self.service.accept(2)
        self.assertEqual(self.service.get_partner(1), 2)
        self.assertEqual(self.service.get_partner(2), 1)

    def test_end_chat(self):
        self.service.create_chat(1, 2)
        self.service.accept(1)
        self.service.accept(2)
        session = self.service.end_chat(1)
        self.assertIsNotNone(session)
        self.assertIsNone(self.service.get_session(1))
        self.assertIsNone(self.service.get_session(2))

    def test_get_partner_no_session(self):
        self.assertIsNone(self.service.get_partner(999))

    def test_stats(self):
        self.assertEqual(self.service.stats()["active_chats"], 0)
        self.service.create_chat(1, 2)
        self.service.accept(1)
        self.service.accept(2)
        self.assertEqual(self.service.stats()["active_chats"], 1)


class TestUnbanRequestRepository(unittest.TestCase):
    DATA_FILE = "test_unban_requests.json"

    def setUp(self):
        self.repo = UnbanRequestRepository()
        self.repo.DATA_FILE = self.DATA_FILE
        self.repo._requests = []
        self.repo._next_id = 1

    def tearDown(self):
        if os.path.exists(self.DATA_FILE):
            os.unlink(self.DATA_FILE)

    def test_add_request(self):
        r = self.repo.add(100, "Прошу разбан")
        self.assertEqual(r.id, 1)
        self.assertEqual(r.user_id, 100)
        self.assertEqual(r.reason, "Прошу разбан")
        self.assertFalse(r.resolved)

    def test_get_unresolved(self):
        self.repo.add(100, "Причина 1")
        self.repo.add(200, "Причина 2")
        self.assertEqual(len(self.repo.get_unresolved()), 2)

    def test_resolve(self):
        r = self.repo.add(100, "Причина")
        resolved = self.repo.resolve(r.id, "accepted")
        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.resolution, "accepted")
        self.assertEqual(len(self.repo.get_unresolved()), 0)

    def test_resolve_nonexistent(self):
        self.assertIsNone(self.repo.resolve(999, "accepted"))

    def test_resolve_already_resolved(self):
        r = self.repo.add(100, "Причина")
        self.repo.resolve(r.id, "accepted")
        result = self.repo.resolve(r.id, "rejected")
        self.assertIsNone(result)

    def test_has_pending(self):
        self.assertFalse(self.repo.has_pending(100))
        self.repo.add(100, "Причина")
        self.assertTrue(self.repo.has_pending(100))

    def test_has_pending_after_resolve(self):
        r = self.repo.add(100, "Причина")
        self.repo.resolve(r.id, "rejected")
        self.assertFalse(self.repo.has_pending(100))

    def test_count_unresolved(self):
        self.repo.add(100, "A")
        r = self.repo.add(200, "B")
        self.assertEqual(self.repo.count_unresolved(), 2)
        self.repo.resolve(r.id, "accepted")
        self.assertEqual(self.repo.count_unresolved(), 1)

    def test_auto_increment_ids(self):
        r1 = self.repo.add(100, "A")
        r2 = self.repo.add(200, "B")
        self.assertEqual(r1.id, 1)
        self.assertEqual(r2.id, 2)


class TestUnbanRequestService(unittest.TestCase):
    def setUp(self):
        self.repo = UnbanRequestRepository()
        self.repo._requests = []
        self.repo._next_id = 1
        self.service = UnbanRequestService(self.repo)

    def test_submit(self):
        r = self.service.submit(100, "Прошу разбан")
        self.assertIsNotNone(r)
        self.assertEqual(r.user_id, 100)

    def test_submit_duplicate_returns_none(self):
        self.service.submit(100, "Первая")
        result = self.service.submit(100, "Вторая")
        self.assertIsNone(result)

    def test_submit_after_resolve(self):
        r = self.service.submit(100, "Первая")
        self.service.resolve(r.id, "rejected")
        r2 = self.service.submit(100, "Вторая")
        self.assertIsNotNone(r2)

    def test_has_pending(self):
        self.assertFalse(self.service.has_pending(100))
        self.service.submit(100, "Причина")
        self.assertTrue(self.service.has_pending(100))

    def test_get_unresolved(self):
        self.service.submit(100, "A")
        self.service.submit(200, "B")
        self.assertEqual(len(self.service.get_unresolved()), 2)

    def test_resolve(self):
        r = self.service.submit(100, "Причина")
        resolved = self.service.resolve(r.id, "accepted")
        self.assertTrue(resolved.resolved)

    def test_count_unresolved(self):
        self.service.submit(100, "A")
        self.assertEqual(self.service.count_unresolved(), 1)


class TestSafeLoadJson(unittest.TestCase):
    TEST_FILE = "test_safe_load.json"

    def tearDown(self):
        for f in [self.TEST_FILE, self.TEST_FILE + ".corrupted"]:
            if os.path.exists(f):
                os.unlink(f)

    def test_missing_file(self):
        result = _safe_load_json("nonexistent.json", default=[])
        self.assertEqual(result, [])

    def test_valid_json(self):
        with open(self.TEST_FILE, "w") as f:
            json.dump([1, 2, 3], f)
        result = _safe_load_json(self.TEST_FILE, default=[])
        self.assertEqual(result, [1, 2, 3])

    def test_corrupted_json(self):
        with open(self.TEST_FILE, "w") as f:
            f.write("{broken json")
        result = _safe_load_json(self.TEST_FILE, default=[])
        self.assertEqual(result, [])
        self.assertTrue(os.path.exists(self.TEST_FILE + ".corrupted"))


class TestAtomicSaveJson(unittest.TestCase):
    TEST_FILE = "test_atomic_save.json"

    def tearDown(self):
        if os.path.exists(self.TEST_FILE):
            os.unlink(self.TEST_FILE)

    def test_write_and_read(self):
        data = {"key": "значение", "list": [1, 2, 3]}
        _atomic_save_json(self.TEST_FILE, data)
        with open(self.TEST_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

    def test_overwrite(self):
        _atomic_save_json(self.TEST_FILE, {"old": True})
        _atomic_save_json(self.TEST_FILE, {"new": True})
        with open(self.TEST_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, {"new": True})


if __name__ == "__main__":
    unittest.main()
