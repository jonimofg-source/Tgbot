from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services import profile_service, match_service

router = Router()


class RegisterState(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()


class EditState(StatesGroup):
    choose_field = State()
    enter_value = State()


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
        [KeyboardButton(text="🔙 В меню")],
    ],
    resize_keyboard=True,
)

EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Имя"), KeyboardButton(text="🎂 Возраст")],
        [KeyboardButton(text="⚧ Пол"), KeyboardButton(text="🔍 Кого ищу")],
        [KeyboardButton(text="🏙 Город"), KeyboardButton(text="📝 О себе")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True, one_time_keyboard=True,
)

CONFIRM_DELETE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Да, удалить"), KeyboardButton(text="❌ Нет, отмена")]],
    resize_keyboard=True, one_time_keyboard=True,
)

GENDER_MAP = {"👨 парень": "male", "👩 девушка": "female"}
LOOKING_MAP = {"👨 парней": "male", "👩 девушек": "female", "💫 всех": "any"}


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
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


@router.message(RegisterState.name)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("⚠️ Введи корректное имя (1–50 символов):")
        return
    await state.update_data(name=name)
    await message.answer("🎂 Сколько тебе лет?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterState.age)


@router.message(RegisterState.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit() or not (14 <= int(text) <= 100):
        await message.answer("⚠️ Введи корректный возраст (14–100):")
        return
    await state.update_data(age=int(text))
    await message.answer("⚧ Укажи свой пол:", reply_markup=GENDER_KB)
    await state.set_state(RegisterState.gender)


@router.message(RegisterState.gender, F.text.casefold().in_(GENDER_MAP))
async def reg_gender(message: Message, state: FSMContext) -> None:
    await state.update_data(gender=GENDER_MAP[message.text.strip().lower()])
    await message.answer("🔍 Кого ты ищешь?", reply_markup=LOOKING_KB)
    await state.set_state(RegisterState.looking_for)


@router.message(RegisterState.gender)
async def reg_gender_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Выбери один из вариантов на клавиатуре.", reply_markup=GENDER_KB)


@router.message(RegisterState.looking_for, F.text.casefold().in_(LOOKING_MAP))
async def reg_looking_for(message: Message, state: FSMContext) -> None:
    await state.update_data(looking_for=LOOKING_MAP[message.text.strip().lower()])
    await message.answer("🏙 Из какого ты города?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterState.city)


@router.message(RegisterState.looking_for)
async def reg_looking_for_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Выбери один из вариантов на клавиатуре.", reply_markup=LOOKING_KB)


@router.message(RegisterState.city)
async def reg_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    if not city or len(city) > 50:
        await message.answer("⚠️ Введи название города (1–50 символов):")
        return
    await state.update_data(city=city)
    await message.answer("📝 Расскажи о себе:")
    await state.set_state(RegisterState.bio)


@router.message(RegisterState.bio)
async def reg_bio(message: Message, state: FSMContext) -> None:
    bio = message.text.strip()
    if not bio or len(bio) > 500:
        await message.answer("⚠️ Введи описание (1–500 символов):")
        return
    data = await state.get_data()
    profile = profile_service.create_profile(
        user_id=message.from_user.id,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        looking_for=data["looking_for"],
        city=data["city"],
        bio=bio,
    )
    await state.clear()
    text = profile_service.format_profile(profile)
    await message.answer(f"🎉 Анкета создана!\n\n{text}", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "👤 Моя анкета")
async def show_my_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    profile = profile_service.get_profile(message.from_user.id)
    if profile is None:
        await message.answer("😔 У тебя ещё нет анкеты. Нажми /start, чтобы создать.")
        return
    text = profile_service.format_profile(profile)
    await message.answer(f"📋 Твоя анкета:\n\n{text}", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "🗑 Удалить анкету")
async def ask_delete_profile(message: Message) -> None:
    if not profile_service.has_profile(message.from_user.id):
        await message.answer("😔 У тебя нет анкеты. Нажми /start, чтобы создать.")
        return
    await message.answer("⚠️ Ты уверен, что хочешь удалить свою анкету?", reply_markup=CONFIRM_DELETE_KB)


@router.message(F.text == "✅ Да, удалить")
async def confirm_delete_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    match_service.cleanup_user(user_id)
    deleted = profile_service.delete_profile(user_id)
    if deleted:
        await message.answer(
            "🗑 Анкета удалена. Нажми /start, чтобы создать новую.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer("😔 Анкета не найдена.", reply_markup=ReplyKeyboardRemove())


@router.message(F.text == "❌ Нет, отмена")
async def cancel_delete(message: Message) -> None:
    await message.answer("👌 Удаление отменено.", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "✏️ Редактировать")
async def start_edit(message: Message, state: FSMContext) -> None:
    if not profile_service.has_profile(message.from_user.id):
        await message.answer("😔 У тебя нет анкеты. Нажми /start, чтобы создать.")
        return
    await message.answer("✏️ Что хочешь изменить?", reply_markup=EDIT_KB)
    await state.set_state(EditState.choose_field)


EDIT_FIELD_MAP = {
    "👤 Имя": "name",
    "🎂 Возраст": "age",
    "⚧ Пол": "gender",
    "🔍 Кого ищу": "looking_for",
    "🏙 Город": "city",
    "📝 О себе": "bio",
}


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
    else:
        await message.answer(f"✏️ Введи новое значение для «{message.text}»:", reply_markup=ReplyKeyboardRemove())

    await state.set_state(EditState.enter_value)


@router.message(EditState.choose_field)
async def edit_choose_field_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Выбери поле на клавиатуре или нажми ❌ Отмена.", reply_markup=EDIT_KB)


@router.message(EditState.enter_value)
async def edit_enter_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field_name = data["edit_field"]
    value = message.text.strip()

    if field_name == "age":
        if not value.isdigit() or not (14 <= int(value) <= 100):
            await message.answer("⚠️ Введи корректный возраст (14–100):")
            return
        value = int(value)
    elif field_name == "gender":
        key = value.lower()
        if key not in GENDER_MAP:
            await message.answer("⚠️ Выбери вариант на клавиатуре.", reply_markup=GENDER_KB)
            return
        value = GENDER_MAP[key]
    elif field_name == "looking_for":
        key = value.lower()
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
        text = profile_service.format_profile(profile)
        await message.answer(f"✅ Анкета обновлена!\n\n{text}", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("😔 Ошибка обновления анкеты.", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "💘 Смотреть анкеты")
async def browse_profiles(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    if not profile_service.has_profile(user_id):
        await message.answer("😔 Сначала создай анкету. Нажми /start.")
        return
    candidate = match_service.get_next_profile(user_id)
    if candidate is None:
        await message.answer("😴 Анкеты закончились. Загляни позже!", reply_markup=MAIN_MENU_KB)
        return
    await state.update_data(current_candidate=candidate.user_id)
    text = profile_service.format_profile(candidate)
    await message.answer(text, reply_markup=BROWSE_KB)


@router.message(F.text == "❤️ Лайк")
async def like_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("⚠️ Сначала нажми «💘 Смотреть анкеты».", reply_markup=MAIN_MENU_KB)
        return

    user_id = message.from_user.id
    is_match = match_service.like(user_id, candidate_id)

    if is_match:
        candidate = profile_service.get_profile(candidate_id)
        candidate_name = candidate.name if candidate else "Кто-то"
        await message.answer(
            f"🎉💘 У вас взаимная симпатия с {candidate_name}! Можете написать друг другу."
        )

    next_candidate = match_service.get_next_profile(user_id)
    if next_candidate is None:
        await state.update_data(current_candidate=None)
        await message.answer("😴 Анкеты закончились. Загляни позже!", reply_markup=MAIN_MENU_KB)
        return

    await state.update_data(current_candidate=next_candidate.user_id)
    text = profile_service.format_profile(next_candidate)
    await message.answer(text, reply_markup=BROWSE_KB)


@router.message(F.text == "👎 Пропустить")
async def skip_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("⚠️ Сначала нажми «💘 Смотреть анкеты».", reply_markup=MAIN_MENU_KB)
        return

    user_id = message.from_user.id
    match_service.skip(user_id, candidate_id)

    next_candidate = match_service.get_next_profile(user_id)
    if next_candidate is None:
        await state.update_data(current_candidate=None)
        await message.answer("😴 Анкеты закончились. Загляни позже!", reply_markup=MAIN_MENU_KB)
        return

    await state.update_data(current_candidate=next_candidate.user_id)
    text = profile_service.format_profile(next_candidate)
    await message.answer(text, reply_markup=BROWSE_KB)


@router.message(F.text == "🔙 В меню")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    if profile_service.has_profile(message.from_user.id):
        await message.answer("📋 Главное меню.", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("😔 Нажми /start, чтобы создать анкету.", reply_markup=ReplyKeyboardRemove())
