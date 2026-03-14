import html
import logging
import time

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services import (
    is_admin, profile_service, match_service, report_service, chat_service,
)

admin_router = Router()
logger = logging.getLogger(__name__)


class AdminBanState(StatesGroup):
    enter_id = State()


class AdminUnbanState(StatesGroup):
    enter_id = State()


ADMIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📋 Жалобы")],
        [KeyboardButton(text="🔨 Бан"), KeyboardButton(text="🔓 Разбан")],
        [KeyboardButton(text="🔙 Выход из админки")],
    ],
    resize_keyboard=True,
)

USER_MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="💘 Смотреть анкеты")],
        [KeyboardButton(text="✏️ Редактировать"), KeyboardButton(text="🗑 Удалить анкету")],
    ],
    resize_keyboard=True,
)


# ============================================================
# /admin
# ============================================================

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У тебя нет доступа к админке.")
        return
    await state.clear()
    await message.answer("🔧 Админ-панель:", reply_markup=ADMIN_MENU_KB)


# ============================================================
# Статистика
# ============================================================

@admin_router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    p_stats = profile_service.stats()
    m_stats = match_service.stats()
    c_stats = chat_service.stats()
    unresolved = report_service.count_unresolved()

    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего анкет: {p_stats['total']}\n"
        f"📷 С фото: {p_stats['with_photo']}\n"
        f"🚫 Забанено: {p_stats['banned']}\n"
        f"❤️ Всего лайков: {m_stats['total_likes']}\n"
        f"💬 Активных чатов: {c_stats['active_chats']}\n"
        f"⚠️ Нерешённых жалоб: {unresolved}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=ADMIN_MENU_KB)


# ============================================================
# Жалобы
# ============================================================

def _format_report_text(report, reported_name: str, total_reports: int) -> str:
    ts = time.strftime("%d.%m.%Y %H:%M", time.localtime(report.timestamp))
    return (
        f"⚠️ <b>Жалоба #{report.id}</b>\n"
        f"📅 {ts}\n"
        f"👤 На: {reported_name} (ID: <code>{report.reported_user}</code>)\n"
        f"📊 Всего жалоб на профиль: {total_reports}\n"
        f"📝 Причина: {html.escape(report.reason)}\n"
        f"👤 От: <code>{report.from_user}</code>"
    )


@admin_router.message(F.text == "📋 Жалобы")
async def admin_reports(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    reports = report_service.get_unresolved()
    if not reports:
        await message.answer("✅ Нет нерешённых жалоб.", reply_markup=ADMIN_MENU_KB)
        return

    for report in reports[:10]:
        reported = profile_service.get_profile(report.reported_user)
        reported_name = html.escape(reported.name) if reported else "удалён"
        total_reports = report_service.count_for_user(report.reported_user)

        text = _format_report_text(report, reported_name, total_reports)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отклонить", callback_data=f"report_dismiss_{report.id}"),
                InlineKeyboardButton(text="🔨 Бан", callback_data=f"report_ban_{report.id}"),
            ],
            [
                InlineKeyboardButton(text="👤 Анкета", callback_data=f"report_view_{report.reported_user}"),
            ],
        ])

        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    if len(reports) > 10:
        await message.answer(f"... и ещё {len(reports) - 10} жалоб.")


@admin_router.callback_query(F.data.startswith("report_dismiss_"))
async def report_dismiss(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа.")
        return

    report_id = int(callback.data.split("_")[-1])
    report = report_service.resolve(report_id, "dismissed")

    if report:
        reported = profile_service.get_profile(report.reported_user)
        reported_name = html.escape(reported.name) if reported else "удалён"
        total_reports = report_service.count_for_user(report.reported_user)
        original_text = _format_report_text(report, reported_name, total_reports)

        await callback.answer("✅ Жалоба отклонена.")
        await callback.message.edit_text(
            original_text + "\n\n✅ <b>Отклонена</b>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await callback.answer("⚠️ Жалоба не найдена.")


@admin_router.callback_query(F.data.startswith("report_ban_"))
async def report_ban(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа.")
        return

    report_id = int(callback.data.split("_")[-1])
    report = report_service.resolve(report_id, "banned")

    if report is None:
        await callback.answer("⚠️ Жалоба не найдена.")
        return

    banned = profile_service.ban_user(report.reported_user)
    chat_service.end_chat(report.reported_user)

    if banned:
        reported = profile_service.get_profile(report.reported_user)
        reported_name = html.escape(reported.name) if reported else "удалён"
        total_reports = report_service.count_for_user(report.reported_user)
        original_text = _format_report_text(report, reported_name, total_reports)

        await callback.answer("🔨 Пользователь забанен.")
        await callback.message.edit_text(
            original_text + "\n\n🔨 <b>Забанен</b>",
            parse_mode=ParseMode.HTML,
        )
        try:
            await callback.bot.send_message(
                report.reported_user,
                "🚫 Ваш аккаунт заблокирован администратором за нарушение правил.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception:
            pass
    else:
        await callback.answer("⚠️ Профиль не найден.")


@admin_router.callback_query(F.data.startswith("report_view_"))
async def report_view_profile(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа.")
        return

    user_id = int(callback.data.split("_")[-1])
    profile = profile_service.get_profile(user_id)

    if profile is None:
        await callback.answer("😔 Профиль не найден.")
        return

    await callback.answer()
    text = profile_service.format_profile(profile)
    status = "🚫 ЗАБАНЕН" if profile.banned else "✅ Активен"
    total_reports = report_service.count_for_user(user_id)
    full_text = f"{text}\n\n📊 Статус: {status}\n⚠️ Жалоб: {total_reports}\n🆔 ID: {user_id}"

    if profile.photo_id:
        await callback.bot.send_photo(
            callback.from_user.id,
            photo=profile.photo_id,
            caption=full_text,
        )
    else:
        await callback.bot.send_message(callback.from_user.id, full_text)


# ============================================================
# Бан / Разбан
# ============================================================

@admin_router.message(F.text == "🔨 Бан")
async def admin_ban_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔨 Введи ID пользователя для бана:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminBanState.enter_id)


@admin_router.message(AdminBanState.enter_id, F.text)
async def admin_ban_execute(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("⚠️ Введи числовой ID:")
        return

    user_id = int(text)

    if is_admin(user_id):
        await message.answer("⚠️ Нельзя забанить администратора.", reply_markup=ADMIN_MENU_KB)
        await state.clear()
        return

    banned = profile_service.ban_user(user_id)
    await state.clear()

    if banned:
        chat_service.end_chat(user_id)
        await message.answer(f"🔨 Пользователь {user_id} забанен.", reply_markup=ADMIN_MENU_KB)
        try:
            await message.bot.send_message(
                user_id,
                "🚫 Ваш аккаунт заблокирован администратором.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception:
            pass
    else:
        await message.answer(f"⚠️ Профиль {user_id} не найден.", reply_markup=ADMIN_MENU_KB)


@admin_router.message(F.text == "🔓 Разбан")
async def admin_unban_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔓 Введи ID пользователя для разбана:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminUnbanState.enter_id)


@admin_router.message(AdminUnbanState.enter_id, F.text)
async def admin_unban_execute(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("⚠️ Введи числовой ID:")
        return

    user_id = int(text)
    unbanned = profile_service.unban_user(user_id)
    await state.clear()

    if unbanned:
        await message.answer(f"🔓 Пользователь {user_id} разбанен.", reply_markup=ADMIN_MENU_KB)
        try:
            await message.bot.send_message(
                user_id,
                "✅ Ваш аккаунт разблокирован. Нажмите /start.",
            )
        except Exception:
            pass
    else:
        await message.answer(f"⚠️ Профиль {user_id} не найден.", reply_markup=ADMIN_MENU_KB)


# ============================================================
# Выход
# ============================================================

@admin_router.message(F.text == "🔙 Выход из админки")
async def admin_exit(message: Message, state: FSMContext) -> None:
    await state.clear()
    if profile_service.has_profile(message.from_user.id):
        await message.answer("📋 Главное меню.", reply_markup=USER_MAIN_MENU_KB)
    else:
        await message.answer("📋 Нажми /start.", reply_markup=ReplyKeyboardRemove())
