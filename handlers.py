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
    keyboard=[[KeyboardButton(text="Male"), KeyboardButton(text="Female")]],
    resize_keyboard=True, one_time_keyboard=True,
)

LOOKING_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Male"), KeyboardButton(text="Female")],
        [KeyboardButton(text="Any")],
    ],
    resize_keyboard=True, one_time_keyboard=True,
)

MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="My profile"), KeyboardButton(text="Browse")],
        [KeyboardButton(text="Edit profile"), KeyboardButton(text="Delete profile")],
    ],
    resize_keyboard=True,
)

BROWSE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Like"), KeyboardButton(text="Skip")],
        [KeyboardButton(text="Back to menu")],
    ],
    resize_keyboard=True,
)

EDIT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Name"), KeyboardButton(text="Age")],
        [KeyboardButton(text="Gender"), KeyboardButton(text="Looking for")],
        [KeyboardButton(text="City"), KeyboardButton(text="Bio")],
        [KeyboardButton(text="Cancel")],
    ],
    resize_keyboard=True, one_time_keyboard=True,
)

CONFIRM_DELETE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Yes, delete"), KeyboardButton(text="No, cancel")]],
    resize_keyboard=True, one_time_keyboard=True,
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    if profile_service.has_profile(user_id):
        await message.answer("Welcome back! Use the menu below.", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer(
            "Welcome to the Dating Bot!\nLet's create your profile.\n\nEnter your name:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(RegisterState.name)


@router.message(RegisterState.name)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) > 50:
        await message.answer("Please enter a valid name (1-50 characters):")
        return
    await state.update_data(name=name)
    await message.answer("Enter your age:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterState.age)


@router.message(RegisterState.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit() or not (14 <= int(text) <= 100):
        await message.answer("Please enter a valid age (14-100):")
        return
    await state.update_data(age=int(text))
    await message.answer("Select your gender:", reply_markup=GENDER_KB)
    await state.set_state(RegisterState.gender)


@router.message(RegisterState.gender, F.text.casefold().in_({"male", "female"}))
async def reg_gender(message: Message, state: FSMContext) -> None:
    await state.update_data(gender=message.text.strip().lower())
    await message.answer("Who are you looking for?", reply_markup=LOOKING_KB)
    await state.set_state(RegisterState.looking_for)


@router.message(RegisterState.gender)
async def reg_gender_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("Please select Male or Female.", reply_markup=GENDER_KB)


@router.message(RegisterState.looking_for, F.text.casefold().in_({"male", "female", "any"}))
async def reg_looking_for(message: Message, state: FSMContext) -> None:
    await state.update_data(looking_for=message.text.strip().lower())
    await message.answer("Enter your city:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterState.city)


@router.message(RegisterState.looking_for)
async def reg_looking_for_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("Please select Male, Female, or Any.", reply_markup=LOOKING_KB)


@router.message(RegisterState.city)
async def reg_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    if not city or len(city) > 50:
        await message.answer("Please enter a valid city name (1-50 characters):")
        return
    await state.update_data(city=city)
    await message.answer("Write something about yourself (bio):")
    await state.set_state(RegisterState.bio)


@router.message(RegisterState.bio)
async def reg_bio(message: Message, state: FSMContext) -> None:
    bio = message.text.strip()
    if not bio or len(bio) > 500:
        await message.answer("Please enter a bio (1-500 characters):")
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
    await message.answer(f"Profile created!\n\n{text}", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "My profile")
async def show_my_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    profile = profile_service.get_profile(message.from_user.id)
    if profile is None:
        await message.answer("You don't have a profile yet. Use /start to create one.")
        return
    text = profile_service.format_profile(profile)
    await message.answer(f"Your profile:\n\n{text}", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "Delete profile")
async def ask_delete_profile(message: Message) -> None:
    if not profile_service.has_profile(message.from_user.id):
        await message.answer("You don't have a profile. Use /start to create one.")
        return
    await message.answer("Are you sure you want to delete your profile?", reply_markup=CONFIRM_DELETE_KB)


@router.message(F.text == "Yes, delete")
async def confirm_delete_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    match_service.cleanup_user(user_id)
    deleted = profile_service.delete_profile(user_id)
    if deleted:
        await message.answer("Your profile has been deleted. Use /start to create a new one.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("No profile found.", reply_markup=ReplyKeyboardRemove())


@router.message(F.text == "No, cancel")
async def cancel_delete(message: Message) -> None:
    await message.answer("Deletion cancelled.", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "Edit profile")
async def start_edit(message: Message, state: FSMContext) -> None:
    if not profile_service.has_profile(message.from_user.id):
        await message.answer("You don't have a profile. Use /start to create one.")
        return
    await message.answer("What do you want to edit?", reply_markup=EDIT_KB)
    await state.set_state(EditState.choose_field)


@router.message(EditState.choose_field, F.text == "Cancel")
async def edit_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Edit cancelled.", reply_markup=MAIN_MENU_KB)


@router.message(EditState.choose_field, F.text.in_({"Name", "Age", "Gender", "Looking for", "City", "Bio"}))
async def edit_choose_field(message: Message, state: FSMContext) -> None:
    field_map = {
        "Name": "name",
        "Age": "age",
        "Gender": "gender",
        "Looking for": "looking_for",
        "City": "city",
        "Bio": "bio",
    }
    field_name = field_map[message.text]
    await state.update_data(edit_field=field_name)

    if field_name == "gender":
        await message.answer("Select new gender:", reply_markup=GENDER_KB)
    elif field_name == "looking_for":
        await message.answer("Select who you are looking for:", reply_markup=LOOKING_KB)
    else:
        await message.answer(f"Enter new value for {message.text}:", reply_markup=ReplyKeyboardRemove())

    await state.set_state(EditState.enter_value)


@router.message(EditState.choose_field)
async def edit_choose_field_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("Please select a field from the keyboard or press Cancel.", reply_markup=EDIT_KB)


@router.message(EditState.enter_value)
async def edit_enter_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field_name = data["edit_field"]
    value = message.text.strip()

    if field_name == "age":
        if not value.isdigit() or not (14 <= int(value) <= 100):
            await message.answer("Please enter a valid age (14-100):")
            return
        value = int(value)
    elif field_name == "gender":
        if value.lower() not in ("male", "female"):
            await message.answer("Please select Male or Female.", reply_markup=GENDER_KB)
            return
        value = value.lower()
    elif field_name == "looking_for":
        if value.lower() not in ("male", "female", "any"):
            await message.answer("Please select Male, Female, or Any.", reply_markup=LOOKING_KB)
            return
        value = value.lower()
    elif field_name == "name":
        if not value or len(value) > 50:
            await message.answer("Please enter a valid name (1-50 characters):")
            return
    elif field_name == "city":
        if not value or len(value) > 50:
            await message.answer("Please enter a valid city (1-50 characters):")
            return
    elif field_name == "bio":
        if not value or len(value) > 500:
            await message.answer("Please enter a valid bio (1-500 characters):")
            return

    profile = profile_service.update_profile(message.from_user.id, **{field_name: value})
    await state.clear()
    if profile:
        text = profile_service.format_profile(profile)
        await message.answer(f"Profile updated!\n\n{text}", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("Error updating profile.", reply_markup=MAIN_MENU_KB)


@router.message(F.text == "Browse")
async def browse_profiles(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    if not profile_service.has_profile(user_id):
        await message.answer("You need a profile first. Use /start to create one.")
        return
    candidate = match_service.get_next_profile(user_id)
    if candidate is None:
        await message.answer("No more profiles to show. Check back later!", reply_markup=MAIN_MENU_KB)
        return
    await state.update_data(current_candidate=candidate.user_id)
    text = profile_service.format_profile(candidate)
    await message.answer(text, reply_markup=BROWSE_KB)


@router.message(F.text == "Like")
async def like_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("No profile selected. Press Browse first.", reply_markup=MAIN_MENU_KB)
        return

    user_id = message.from_user.id
    is_match = match_service.like(user_id, candidate_id)

    if is_match:
        candidate = profile_service.get_profile(candidate_id)
        candidate_name = candidate.name if candidate else "Someone"
        await message.answer(f"It's a match with {candidate_name}! You can message each other now.")

    next_candidate = match_service.get_next_profile(user_id)
    if next_candidate is None:
        await state.update_data(current_candidate=None)
        await message.answer("No more profiles to show. Check back later!", reply_markup=MAIN_MENU_KB)
        return

    await state.update_data(current_candidate=next_candidate.user_id)
    text = profile_service.format_profile(next_candidate)
    await message.answer(text, reply_markup=BROWSE_KB)


@router.message(F.text == "Skip")
async def skip_profile(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    candidate_id = data.get("current_candidate")
    if candidate_id is None:
        await message.answer("No profile selected. Press Browse first.", reply_markup=MAIN_MENU_KB)
        return

    user_id = message.from_user.id
    match_service.skip(user_id, candidate_id)

    next_candidate = match_service.get_next_profile(user_id)
    if next_candidate is None:
        await state.update_data(current_candidate=None)
        await message.answer("No more profiles to show. Check back later!", reply_markup=MAIN_MENU_KB)
        return

    await state.update_data(current_candidate=next_candidate.user_id)
    text = profile_service.format_profile(next_candidate)
    await message.answer(text, reply_markup=BROWSE_KB)


@router.message(F.text == "Back to menu")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    if profile_service.has_profile(message.from_user.id):
        await message.answer("Main menu.", reply_markup=MAIN_MENU_KB)
    else:
        await message.answer("Use /start to create a profile.", reply_markup=ReplyKeyboardRemove())
