import html
import logging

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.base import StorageKey

from services import profile_service, match_service, report_service, chat_service, unban_service

router = Router()
logger = logging.getLogger(__name__)


# --- FSM States ---

class RegisterState(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()
    photo = State()


class EditState(StatesGroup):
    choose_field = State()
    enter_value = State()


class ReportState(StatesGroup):
    reason = State()
    photo = State()


class UnbanAppealState(StatesGroup):
    reason = State()


class ChatState(StatesGroup):
    active = State()


# --- Keyboards ---

GENDER_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="👨 Парень"), KeyboardButton(text="👩 Девушка")]],
    resize_keyboard=True, one_time_keyboard=True,
)

LOOKING_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨 Парней"), KeyboardButton(text="👩 Девушек")],
        [KeyboardButton(text="💫 Всех")],
    ],
    resize_keyboard=True, one_time_keyboard=True,
)

MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="💘 Смотреть анкеты")],
        [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="🗑 Удалить анкету")],
    ],
    resize_keyboard=True,
)

BROWSE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❤️ Лайк"), KeyboardButton(text="👎 Пропустить")],
        [KeyboardButton(text="⚠️ Жалоба"), KeyboardButton(text="🔙 В меню")],
    ],
    resize_keyboard=True,
)

EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Имя"), KeyboardButton(text="🎂 Возраст")],
        [KeyboardButton(text="⚧ Пол"), KeyboardButton(text="🔍 Кого ищу")],
        [KeyboardButton(text="🏙 Город"), KeyboardButton(text="📝 О себе")],
        [KeyboardButton(text="📷 Фото"), KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True, one_time_keyboard=True,
)

CONFIRM_DELETE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Да, удалить"), KeyboardButton(text="❌ Нет, отмена")]],
    resize_keyboard=True, one_time_keyboard=True,
)

PHOTO_SKIP_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏩ Пропустить фото")]],
    resize_keyboard=True, one_time_keyboard=True,
)

CHAT_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚪 Завершить чат")]],
    resize_keyboard=True,
)

REPORT_PHOTO_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏩ Без фото")]],
    resize_keyboard=True, one_time_keyboard=True,
)

BANNED_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📨 Подать заявку на разбан")]],
    resize_keyboard=True, one_time_keyboard=True,
)

# --- Maps ---

GENDER_MAP = {"👨 парень": "male", "👩 девушка": "female"}
LOOKING_MAP = {"👨 парней": "male", "👩 девушек": "female", "💫 всех": "any"}

EDIT_FIELD_MAP = {
    "👤 Имя": "name",
    "🎂 Возраст": "age",
    "⚧ Пол": "gender",
    "🔍 Кого ищу": "looking_for",
    "🏙 Город": "city",
    "📝 О себе": "bio",
    "📷 Фото": "photo",
}


def _normalize(text: str) -> str:
    return text.strip().casefold()


def _partner_fsm(state: FSMContext, bot_id: int, partner_id: int) -> FSMContext:
    """Create an FSMContext for another user to set/clear their state."""
    key = StorageKey(bot_id=bot_id, chat_id=partner_id, user_id=partner_id)
    return FSMContext(storage=state.storage, key=key)


async def _send_profile(message: Message, profile, reply_markup=None):
    """Send profile with or without photo."""
    text = profile_service.format_profile(profile)
    if profile.photo_id:
        await message.answer_photo(
            photo=profile.photo_id,
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        await message.answer(text, reply_markup=reply_markup)


# ============================================================
# /start
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id

    if profile_service.is_banned(user_id):
        if unban_service.has_pending(user_id):
            await message.answer(
                "🚫 Ваш аккаунт заблокирован.\n"
                "📨 Ваша заявка на разбан уже отправлена. Ожидайте решения.",
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            await message.answer(
                "🚫 Ваш аккаунт заблокирован.\n"
                "Вы можете подать заявку на разбан.",
                reply_markup=BANNED_KB,
            )
        return

    if profile_service.has_profile(user_id):
        await message.answer("👋 С возвращением! Выбери действие в меню.", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer(
            "👋 Привет! Добро пожаловать в бот знакомств!\n"
            "Давай создадим твою анкету.\n\n"
            "✏️ Введи своё имя:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(RegisterState.name)


# ============================================================
# Регистрация
# ============================================================

@router.message(RegisterState.name, F.text)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("⚠️ Введи корректное имя (1–50 символов):")
        return
    await state.update_data(name=name)
    await message.answer("🎂 Сколько тебе лет?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterState.age)


@router.message(RegisterState.name)
async def reg_name_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Пожалуйста, отправь текстовое сообщение с именем:")


@router.message(RegisterState.age, F.text)
async def reg_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit() or not (14 <= int(text) <= 100):
        await message.answer("⚠️ Введи корректный возраст (14–100):")
        return
    await state.update_data(age=int(text))
    await message.answer("⚧ Укажи свой пол:", reply_markup=GENDER_KB)
    await state.set_state(RegisterState.gender)


@router.message(RegisterState.age)
async def reg_age_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Отправь число — свой возраст (14–100):")


@router.message(RegisterState.gender, F.text.casefold().in_(GENDER_MAP))
async def reg_gender(message: Message, state: FSMContext) -> None:
    await state.update_data(gender=GENDER_MAP[_normalize(message.text)])
    await message.answer("🔍 Кого ты ищешь?", reply_markup=LOOKING_KB)
    await state.set_state(RegisterState.looking_for)


@router.message(RegisterState.gender)
async def reg_gender_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Выбери один из вариантов на клавиатуре.", reply_markup=GENDER_KB)


@router.message(RegisterState.looking_for, F.text.casefold().in_(LOOKING_MAP))
async def reg_looking_for(message: Message, state: FSMContext) -> None:
    await state.update_data(looking_for=LOOKING_MAP[_normalize(message.text)])
    await message.answer("🏙 Из какого ты города?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterState.city)


@router.message(RegisterState.looking_for)
async def reg_looking_for_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Выбери один из вариантов на клавиатуре.", reply_markup=LOOKING_KB)


@router.message(RegisterState.city, F.text)
async def reg_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    if not city or len(city) > 50:
        await message.answer("⚠️ Введи название города (1–50 символов):")
        return
    await state.update_data(city=city)
    await message.answer("📝 Расскажи о себе:")
    await state.set_state(RegisterState.bio)


@router.message(RegisterState.city)
async def reg_city_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Пожалуйста, отправь текстовое сообщение с названием города:")


@router.message(RegisterState.bio, F.text)
async def reg_bio(message: Message, state: FSMContext) -> None:
    bio = message.text.strip()
    if not bio or len(bio) > 500:
        await message.answer("⚠️ Введи описание (1–500 символов):")
        return
    await state.update_data(bio=bio)
    await message.answer(
        "📷 Отправь фото профиля или нажми «Пропустить»:",
        reply_markup=PHOTO_SKIP_KB,
    )
    await state.set_state(RegisterState.photo)


@router.message(RegisterState.bio)
async def reg_bio_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Пожалуйста, отправь текстовое описание о себе:")


@router.message(RegisterState.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    await _finish_registration(message, state, photo_id=photo_id)


@router.message(RegisterState.photo, F.text == "⏩ Пропустить фото")
async def reg_photo_skip(message: Message, state: FSMContext) -> None:
    await _finish_registration(message, state, photo_id=None)


@router.message(RegisterState.photo)
async def reg_photo_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Отправь фото или нажми «⏩ Пропустить фото»:", reply_markup=PHOTO_SKIP_KB)


async def _finish_registration(message: Message, state: FSMContext, photo_id: str | None) -> None:
    data = await state.get_data()
    profile = profile_service.create_profile(
        user_id=message.from_user.id,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        looking_for=data["looking_for"],
        city=data["city"],
        bio=data["bio"],
        photo_id=photo_id,
    )
    await state.clear()
    await message.answer("🎉 Анкета создана!", reply_markup=MAIN_MENU_KB)
    await _send_profile(message, profile, reply_markup=MAIN_MENU_KB)


# ============================================================
# Главное меню
# ============================================================

@router.message(F.text == "👤 Моя анкета")
async def show_my_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    profile = profile_service.get_profile(message.from_user.id)
    if profile is None:
        await message.answer("😔 У тебя ещё нет анкеты. Нажми /start, чтобы создать.")
        return
    await message.answer("📋 Твоя анкета:")
    await _send_profile(message, profile, reply_markup=MAIN_MENU_KB)


@router.message(F.text == "🗑 Удалить анкету")
async def ask_delete_profile(message: Message, state: FSMContext) -> None:
    if not profile_service.has_profile(message.from_user.id):
        await message.answer("😔 У тебя нет анкеты. Нажми /start, чтобы создать.")
        return
    await state.update_data(confirm_delete=True)
    await message.answer("⚠️ Ты уверен, что хочешь удалить свою анкету?", reply_markup=CONFIRM_DELETE_KB)


@router.message(F.text == "✅ Да, удалить")
async def confirm_delete_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("confirm_delete"):
        await message.answer("📋 Главное меню.", reply_markup=MAIN_MENU_KB)
        return
    await state.clear()
    user_id = message.from_user.id
    chat_service.end_chat(user_id)
    match_service.cleanup_user(user_id)
    report_service.cleanup_user(user_id)
    deleted = profile_service.delete_profile(user_id)
    if deleted:
        await message.answer(
            "🗑 Анкета удалена. Нажми /start, чтобы создать новую.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer("😔 Анкета не найдена.", reply_markup=ReplyKeyboardRemove())


@router.message(F.text == "❌ Нет, отмена")
async def cancel_delete(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("confirm_delete"):
        await message.answer("📋 Главное меню.", reply_markup=MAIN_MENU_KB)
        return
    await state.clear()
    await message.answer("👌 Удаление отменено.", reply_markup=MAIN_MENU_KB)


# ============================================================
# Редактирование
# ============================================================

@router.message(F.text == "✏️ Редактировать")
async def start_edit(message: Message, state: FSMContext) -> None:
    if not profile_service.has_profile(message.from_user.id):
        await message.answer("😔 У тебя нет анкеты. Нажми /start, чтобы создать.")
        return
    await message.answer("✏️ Что хочешь изменить?", reply_markup=EDIT_KB)
    await state.set_state(EditState.choose_field)


@router.message(EditState.choose_field, F.text == "❌ Отмена")
async def edit_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("👌 Редактирование отменено.", reply_markup=MAIN_MENU_KB)


@router.message(EditState.choose_field, F.text.in_(EDIT_FIELD_MAP))
async def edit_choose_field(message: Message, state: FSMContext) -> None:
    field_name = EDIT_FIELD_MAP[message.text]
    await state.update_data(edit_field=field_name)

    if field_name == "gender":
        await message.answer("⚧ Выбери новый пол:", reply_markup=GENDER_KB)
    elif field_name == "looking_for":
        await message.answer("🔍 Кого теперь ищешь?", reply_markup=LOOKING_KB)
    elif field_name == "photo":
        await message.answer("📷 Отправь новое фото профиля:", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(f"✏️ Введи новое значение для «{message.text}»:", reply_markup=ReplyKeyboardRemove())

    await state.set_state(EditState.enter_value)


@router.message(EditState.choose_field)
async def edit_choose_field_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Выбери поле на клавиатуре или нажми ❌ Отмена.", reply_markup=EDIT_KB)


@router.message(EditState.enter_value, F.photo)
async def edit_enter_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("edit_field") != "photo":
        await message.answer("⚠️ Сейчас ожидается текст, не фото.")
        return
    photo_id = message.photo[-1].file_id
    profile = profile_service.update_profile(message.from_user.id, photo_id=photo_id)
    await state.clear()
    if profile:
        await message.answer("✅ Фото обновлено!", reply_markup=MAIN_MENU_KB)
        await _send_profile(message, profile, reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("😔 Ошибка обновления анкеты.", reply_markup=MAIN_MENU_KB)


@router.message(EditState.enter_value, F.text)
async def edit_enter_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field_name = data["edit_field"]

    if field_name == "photo":
        await message.answer("⚠️ Отправь фото, а не текст.")
        return

    value = message.text.strip()

    if field_name == "age":
        if not value.isdigit() or not (14 <= int(value) <= 100):
            await message.answer("⚠️ Введи корректный возраст (14–100):")
            return
        value = int(value)
    elif field_name == "gender":
        key = _normalize(value)
        if key not in GENDER_MAP:
            await message.answer("⚠️ Выбери вариант на клавиатуре.", reply_markup=GENDER_KB)
            return
        value = GENDER_MAP[key]
    elif field_name == "looking_for":
        key = _normalize(value)
        if key not in LOOKING_MAP:
            await message.answer("⚠️ Выбери вариант на клавиатуре.", reply_markup=LOOKING_KB)
            return
        value = LOOKING_MAP[key]
    elif field_name == "name":
        if not value or len(value) > 50:
            await message.answer("⚠️ Введи корректное имя (1–50 символов):")
            return
    elif field_name == "city":
        if not value or len(value) > 50:
            await message.answer("⚠️ Введи название города (1–50 символов):")
            return
    elif field_name == "bio":
        if not value or len(value) > 500:
            await message.answer("⚠️ Введи описание (1–500 символов):")
            return

    profile = profile_service.update_profile(message.from_user.id, **{field_name: value})
    await state.clear()
    if profile:
        await message.answer("✅ Анкета обновлена!", reply_markup=MAIN_MENU_KB)
        await _send_profile(message, profile, reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("😔 Ошибка обновления анкеты.", reply_markup=MAIN_MENU_KB)


@router.message(EditState.enter_value)
async def edit_enter_value_invalid(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("edit_field") == "photo":
        await message.answer("⚠️ Отправь фото.")
    else:
        await message.answer("⚠️ Пожалуйста, отправь текстовое сообщение:")


# ============================================================
# Просмотр анкет
# ============================================================

@router.message(F.text == "💘 Смотреть анкеты")
async def browse_profiles(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    if not profile_service.has_profile(user_id):
        await message.answer("😔 Сначала создай анкету. Нажми /start.")
        return
    if profile_service.is_banned(user_id):
        await message.answer("🚫 Ваш аккаунт заблокирован.", reply_markup=ReplyKeyboardRemove())
        return
    candidate = match_service.get_next_profile(user_id)
    if candidate is None:
        await message.answer("😴 Анкеты закончились. Загляни позже!", reply_markup=MAIN_MENU_KB)
        return
    await state.update_data(current_candidate=candidate.user_id)
    await _send_profile(message, candidate, reply_markup=BROWSE_KB)


@router.message(F.text == "❤️ Лайк")
async def like_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("⚠️ Сначала нажми «💘 Смотреть анкеты».", reply_markup=MAIN_MENU_KB)
        return

    user_id = message.from_user.id
    await state.update_data(current_candidate=None)

    is_match = match_service.like(user_id, candidate_id)

    if is_match:
        candidate = profile_service.get_profile(candidate_id)
        my_profile = profile_service.get_profile(user_id)
        candidate_name = html.escape(candidate.name) if candidate else "Кто-то"
        my_name = html.escape(my_profile.name) if my_profile else "Кто-то"

        chat_service.create_chat(user_id, candidate_id)

        chat_invite_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Начать чат", callback_data="chat_accept")],
            [InlineKeyboardButton(text="⏩ Пропустить", callback_data="chat_decline")],
        ])

        await message.answer(
            f'🎉💘 У вас взаимная симпатия с '
            f'<a href="tg://user?id={candidate_id}">{candidate_name}</a>!\n'
            f'Хочешь начать чат?',
            parse_mode=ParseMode.HTML,
            reply_markup=chat_invite_kb,
        )
        try:
            await message.bot.send_message(
                candidate_id,
                f'🎉💘 У тебя взаимная симпатия с '
                f'<a href="tg://user?id={user_id}">{my_name}</a>!\n'
                f'Хочешь начать чат?',
                parse_mode=ParseMode.HTML,
                reply_markup=chat_invite_kb,
            )
        except Exception as e:
            logger.warning("Не удалось уведомить %s о мэтче: %s", candidate_id, e)

    next_candidate = match_service.get_next_profile(user_id)
    if next_candidate is None:
        await message.answer("😴 Анкеты закончились. Загляни позже!", reply_markup=MAIN_MENU_KB)
        return

    await state.update_data(current_candidate=next_candidate.user_id)
    await _send_profile(message, next_candidate, reply_markup=BROWSE_KB)


@router.message(F.text == "👎 Пропустить")
async def skip_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("⚠️ Сначала нажми «💘 Смотреть анкеты».", reply_markup=MAIN_MENU_KB)
        return

    user_id = message.from_user.id
    await state.update_data(current_candidate=None)

    match_service.skip(user_id, candidate_id)

    next_candidate = match_service.get_next_profile(user_id)
    if next_candidate is None:
        await message.answer("😴 Анкеты закончились. Загляни позже!", reply_markup=MAIN_MENU_KB)
        return

    await state.update_data(current_candidate=next_candidate.user_id)
    await _send_profile(message, next_candidate, reply_markup=BROWSE_KB)


# ============================================================
# Жалобы
# ============================================================

@router.message(F.text == "⚠️ Жалоба")
async def report_start(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("⚠️ Сначала нажми «💘 Смотреть анкеты».", reply_markup=MAIN_MENU_KB)
        return
    await state.update_data(report_target=candidate_id)
    await state.set_state(ReportState.reason)
    await message.answer(
        "📝 Опиши причину жалобы (1–300 символов):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена жалобы")]],
            resize_keyboard=True, one_time_keyboard=True,
        ),
    )


@router.message(ReportState.reason, F.text == "❌ Отмена жалобы")
async def report_cancel(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    await state.clear()
    if candidate_id:
        await state.update_data(current_candidate=candidate_id)
    await message.answer("👌 Жалоба отменена.", reply_markup=BROWSE_KB)


@router.message(ReportState.reason, F.text)
async def report_reason(message: Message, state: FSMContext) -> None:
    reason = message.text.strip()
    if not reason or len(reason) > 300:
        await message.answer("⚠️ Введи причину (1–300 символов):")
        return

    await state.update_data(report_reason=reason)
    await state.set_state(ReportState.photo)
    await message.answer(
        "📷 Приложи фото-доказательство или нажми «Без фото»:",
        reply_markup=REPORT_PHOTO_KB,
    )


@router.message(ReportState.reason)
async def report_reason_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Отправь текстовое описание причины жалобы:")


@router.message(ReportState.photo, F.photo)
async def report_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    await _submit_report(message, state, photo_id=photo_id)


@router.message(ReportState.photo, F.text == "⏩ Без фото")
async def report_photo_skip(message: Message, state: FSMContext) -> None:
    await _submit_report(message, state, photo_id=None)


@router.message(ReportState.photo)
async def report_photo_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Отправь фото или нажми «⏩ Без фото»:", reply_markup=REPORT_PHOTO_KB)


async def _submit_report(message: Message, state: FSMContext, photo_id: str | None) -> None:
    data = await state.get_data()
    target_id = data.get("report_target")
    reason = data.get("report_reason", "")
    if target_id is None:
        await state.clear()
        await message.answer("⚠️ Ошибка. Попробуй заново.", reply_markup=MAIN_MENU_KB)
        return

    report = report_service.file_report(
        from_user=message.from_user.id,
        reported_user=target_id,
        reason=reason,
        photo_id=photo_id,
    )
    logger.info("Жалоба #%d от %d на %d: %s", report.id, message.from_user.id, target_id, reason)

    user_id = message.from_user.id
    match_service.skip(user_id, target_id)

    await state.clear()
    await message.answer("✅ Жалоба отправлена. Спасибо!", reply_markup=MAIN_MENU_KB)


# ============================================================
# Чат между пользователями
# ============================================================

@router.callback_query(F.data == "chat_accept")
async def chat_accept_callback(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    session = chat_service.accept(user_id)

    if session is None:
        await callback.answer("⏳ Чат больше не доступен.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await callback.answer("✅ Ты принял приглашение!")
    await callback.message.edit_reply_markup(reply_markup=None)

    if session.both_accepted:
        partner_id = session.partner_of(user_id)

        # Set ChatState.active for BOTH users
        await state.set_state(ChatState.active)
        partner_ctx = _partner_fsm(state, callback.bot.id, partner_id)
        await partner_ctx.set_state(ChatState.active)

        await callback.message.answer(
            "💬 Чат начался! Пиши сообщения — они будут пересланы собеседнику.\n"
            "Нажми «🚪 Завершить чат» чтобы выйти.",
            reply_markup=CHAT_KB,
        )
        try:
            await callback.bot.send_message(
                partner_id,
                "💬 Чат начался! Пиши сообщения — они будут пересланы собеседнику.\n"
                "Нажми «🚪 Завершить чат» чтобы выйти.",
                reply_markup=CHAT_KB,
            )
        except Exception as e:
            logger.warning("Не удалось уведомить %s о начале чата: %s", partner_id, e)
    else:
        await callback.message.answer("⏳ Ожидаем ответа собеседника...")


@router.callback_query(F.data == "chat_decline")
async def chat_decline_callback(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    session = chat_service.end_chat(user_id)

    await callback.answer("👌 Ты отклонил чат.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("📋 Главное меню.", reply_markup=MAIN_MENU_KB)

    if session:
        partner_id = session.partner_of(user_id)
        if partner_id:
            # Clear partner's state if they were waiting
            partner_ctx = _partner_fsm(state, callback.bot.id, partner_id)
            await partner_ctx.clear()
            try:
                await callback.bot.send_message(
                    partner_id,
                    "😔 Собеседник отклонил приглашение в чат.",
                    reply_markup=MAIN_MENU_KB,
                )
            except Exception:
                pass


@router.message(ChatState.active, F.text == "🚪 Завершить чат")
async def chat_end(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    session = chat_service.end_chat(user_id)
    await state.clear()
    await message.answer("🚪 Чат завершён.", reply_markup=MAIN_MENU_KB)

    if session:
        partner_id = session.partner_of(user_id)
        if partner_id:
            # Clear partner's ChatState.active so they don't stay stuck
            partner_ctx = _partner_fsm(state, message.bot.id, partner_id)
            await partner_ctx.clear()
            try:
                await message.bot.send_message(
                    partner_id,
                    "🚪 Собеседник завершил чат.",
                    reply_markup=MAIN_MENU_KB,
                )
            except Exception:
                pass


@router.message(ChatState.active, F.text)
async def chat_relay_text(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    partner_id = chat_service.get_partner(user_id)

    if partner_id is None:
        await state.clear()
        await message.answer("⚠️ Чат не активен.", reply_markup=MAIN_MENU_KB)
        return

    my_profile = profile_service.get_profile(user_id)
    sender_name = my_profile.name if my_profile else "Аноним"

    try:
        await message.bot.send_message(
            partner_id,
            f"💬 {html.escape(sender_name)}:\n{html.escape(message.text)}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("Не удалось переслать сообщение %s: %s", partner_id, e)
        await message.answer("⚠️ Не удалось отправить сообщение.")


@router.message(ChatState.active, F.photo)
async def chat_relay_photo(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    partner_id = chat_service.get_partner(user_id)

    if partner_id is None:
        await state.clear()
        await message.answer("⚠️ Чат не активен.", reply_markup=MAIN_MENU_KB)
        return

    my_profile = profile_service.get_profile(user_id)
    sender_name = my_profile.name if my_profile else "Аноним"
    caption = f"📷 от {html.escape(sender_name)}"
    if message.caption:
        caption += f"\n{html.escape(message.caption)}"

    try:
        await message.bot.send_photo(
            partner_id,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("Не удалось переслать фото %s: %s", partner_id, e)
        await message.answer("⚠️ Не удалось отправить фото.")


@router.message(ChatState.active, F.sticker)
async def chat_relay_sticker(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    partner_id = chat_service.get_partner(user_id)

    if partner_id is None:
        await state.clear()
        await message.answer("⚠️ Чат не активен.", reply_markup=MAIN_MENU_KB)
        return

    try:
        await message.bot.send_sticker(partner_id, sticker=message.sticker.file_id)
    except Exception as e:
        logger.warning("Не удалось переслать стикер %s: %s", partner_id, e)
        await message.answer("⚠️ Не удалось отправить стикер.")


@router.message(ChatState.active, F.voice)
async def chat_relay_voice(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    partner_id = chat_service.get_partner(user_id)

    if partner_id is None:
        await state.clear()
        await message.answer("⚠️ Чат не активен.", reply_markup=MAIN_MENU_KB)
        return

    my_profile = profile_service.get_profile(user_id)
    sender_name = my_profile.name if my_profile else "Аноним"

    try:
        await message.bot.send_voice(
            partner_id,
            voice=message.voice.file_id,
            caption=f"🎤 от {html.escape(sender_name)}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning("Не удалось переслать голосовое %s: %s", partner_id, e)
        await message.answer("⚠️ Не удалось отправить голосовое.")


@router.message(ChatState.active)
async def chat_relay_unsupported(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Этот тип сообщений не поддерживается в чате. Отправь текст, фото, стикер или голосовое.")


# ============================================================
# Навигация
# ============================================================

# ============================================================
# Заявка на разбан
# ============================================================

@router.message(F.text == "📨 Подать заявку на разбан")
async def unban_appeal_start(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    if not profile_service.is_banned(user_id):
        await message.answer("✅ Ваш аккаунт не заблокирован.", reply_markup=MAIN_MENU_KB)
        return
    if unban_service.has_pending(user_id):
        await message.answer(
            "📨 Ваша заявка уже отправлена. Ожидайте решения.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.set_state(UnbanAppealState.reason)
    await message.answer(
        "📝 Напишите причину, по которой вас стоит разбанить (1–500 символов):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True, one_time_keyboard=True,
        ),
    )


@router.message(UnbanAppealState.reason, F.text == "❌ Отмена")
async def unban_appeal_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("👌 Заявка отменена.", reply_markup=BANNED_KB)


@router.message(UnbanAppealState.reason, F.text)
async def unban_appeal_submit(message: Message, state: FSMContext) -> None:
    reason = message.text.strip()
    if not reason or len(reason) > 500:
        await message.answer("⚠️ Введите причину (1–500 символов):")
        return

    user_id = message.from_user.id
    req = unban_service.submit(user_id, reason)
    await state.clear()

    if req:
        logger.info("Заявка на разбан #%d от %d: %s", req.id, user_id, reason)
        await message.answer(
            "✅ Заявка на разбан отправлена. Ожидайте решения администратора.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer(
            "📨 У вас уже есть активная заявка. Ожидайте решения.",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.message(UnbanAppealState.reason)
async def unban_appeal_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Отправьте текстовое сообщение с причиной:")


# ============================================================
# Навигация
# ============================================================

@router.message(F.text == "🔙 В меню")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    if profile_service.has_profile(message.from_user.id):
        await message.answer("📋 Главное меню.", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("😔 Нажми /start, чтобы создать анкету.", reply_markup=ReplyKeyboardRemove())


# --- Fallback ---

@router.message(F.text)
async def fallback_handler(message: Message) -> None:
    await message.answer(
        "🤔 Не понимаю. Используй меню или нажми /start.",
        reply_markup=MAIN_MENU_KB,
    )
