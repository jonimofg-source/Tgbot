from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from services import profile_service, is_admin, unban_service

BANNED_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📨 Подать заявку на разбан")]],
    resize_keyboard=True, one_time_keyboard=True,
)


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        user_id = user.id

        if is_admin(user_id):
            return await handler(event, data)

        if not profile_service.is_banned(user_id):
            return await handler(event, data)

        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        if isinstance(event, Message) and event.text == "📨 Подать заявку на разбан":
            return await handler(event, data)

        state = data.get("state")
        if state:
            current_state = await state.get_state()
            if current_state and "UnbanAppealState" in current_state:
                return await handler(event, data)

        if isinstance(event, Message):
            if unban_service.has_pending(user_id):
                await event.answer(
                    "🚫 Ваш аккаунт заблокирован.\n"
                    "📨 Ваша заявка на разбан уже отправлена. Ожидайте решения.",
                    reply_markup=ReplyKeyboardRemove(),
                )
            else:
                await event.answer(
                    "🚫 Ваш аккаунт заблокирован.\n"
                    "Вы можете подать заявку на разбан.",
                    reply_markup=BANNED_KB,
                )
        elif isinstance(event, CallbackQuery):
            await event.answer("🚫 Ваш аккаунт заблокирован.")

        return
