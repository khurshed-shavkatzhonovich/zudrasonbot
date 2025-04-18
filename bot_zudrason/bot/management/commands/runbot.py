# bot/management/commands/runbot.py
# bot/management/commands/runbot.py
import os
import asyncio
from typing import Optional
from django.core.management.base import BaseCommand
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ContentType
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from django.core.files.base import ContentFile
from asgiref.sync import sync_to_async
from dotenv import load_dotenv

from bot.models import Order

load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN не найден в .env файле!")

class Command(BaseCommand):
    help = 'Запускает Telegram бота Zudrason'
    
    def handle(self, *args, **options):
        asyncio.run(self.main())

    async def main(self):
        # Инициализация бота и диспетчера
        bot = Bot(token=TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        router = Router()
        dp.include_router(router)

        # Константы
        GROUP_ID = -1002665268326  # ID группы оператора
        COURIER_GROUP_ID = -1002648695686  # ID группы курьеров
        PAYMENT_DETAILS = {
            "card_number": "1234567890118038",
            "phone_number": "+992501070777"
        }

        # ======================
        # ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
        # ======================

        def get_main_menu():
            return ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📦 Курьерские услуги")],
                    [KeyboardButton(text="ℹ️ О нас")],
                    [KeyboardButton(text="🛵 Стать курьером")]
                ],
                resize_keyboard=True,
                is_persistent=True
            )

        def get_back_to_menu_button():
            """Возвращает кнопку для возврата в меню"""
            return ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
                resize_keyboard=True
            )

        # ======================
        # СОСТОЯНИЯ
        # ======================

        class OrderForm(StatesGroup):
            from_address = State()
            to_address = State()
            phone = State()
            package_type = State()
            photo = State()

        class PaymentForm(StatesGroup):
            waiting_for_receipt = State()
            confirm_payment = State()

        class CourierStates(StatesGroup):
            waiting_for_courier_message = State()
            waiting_for_delivery_confirmation = State()
            waiting_for_delivery_message = State()
            waiting_for_client_confirmation = State()

        class FeedbackStates(StatesGroup):
            waiting_for_feedback_choice = State()
            waiting_for_feedback_text = State()

        # ======================
        # БАЗА ДАННЫХ
        # ======================

        @sync_to_async
        def create_order(user_id: int, username: str, from_address: str, to_address: str, 
                        phone: str, package_type: str, photo: Optional[ContentFile] = None, 
                        photo_file_id: Optional[str] = None) -> int:
            order = Order(
                user_id=user_id,
                client_link=f"https://t.me/{username}" if username else None,
                from_address=from_address,
                to_address=to_address,
                phone=phone,
                package_type=package_type,
                status='pending'
            )
            if photo:
                order.photo.save(f"order_{user_id}_{order.id}.jpg", photo, save=False)
            if photo_file_id:
                order.photo_file_id = photo_file_id
            order.save()
            return order.id

        @sync_to_async
        def get_order_by_id(order_id: int) -> Optional[Order]:
            try:
                return Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                return None

        @sync_to_async
        def set_order_price(order_id: int, price: float) -> None:
            order = Order.objects.get(id=order_id)
            order.price = price
            order.save()

        @sync_to_async
        def confirm_order(order_id: int) -> None:
            order = Order.objects.get(id=order_id)
            order.status = 'confirmed'
            order.save()

        @sync_to_async
        def assign_courier(order_id: int, courier_id: int, courier_username: str):
            order = Order.objects.get(id=order_id)
            order.courier_id = courier_id
            order.courier_link = f"https://t.me/{courier_username}" if courier_username else None
            order.status = 'assigned'
            order.save()
            return order

        @sync_to_async
        def update_order_status(order_id: int, status: str):
            order = Order.objects.get(id=order_id)
            order.status = status
            order.save()
            return order

        @sync_to_async
        def set_courier_message(order_id: int, message: str):
            order = Order.objects.get(id=order_id)
            order.courier_message = message
            order.save()
            return order

        @sync_to_async
        def set_delivery_message(order_id: int, message: str):
            order = Order.objects.get(id=order_id)
            order.delivery_message = message
            order.status = 'delivered'
            order.save()
            return order

        # ======================
        # ОСНОВНЫЕ КОМАНДЫ
        # ======================

        # Обработчики должны быть объявлены как обычные функции, а затем зарегистрированы
        async def start_handler(message: Message):
            await message.answer(
                "🚀 Добро пожаловать в Zudrason! 📦\n"
                "Мы доставляем еду, лекарства, посылки и всё, что вам нужно.\n"
                "Выберите категорию, чтобы начать!",
                reply_markup=get_main_menu()
            )

        async def back_to_main_handler(message: Message):
            await start_handler(message)

        async def about_us_handler(message: Message):
            await message.answer(
                """🚀 Zudrason — это современный сервис курьерской доставки.
                Мы работаем, чтобы ваши посылки доходили быстро и безопасно!""",
                reply_markup=get_main_menu()
            )

        async def become_courier_handler(message: Message):
            await message.answer(
                "Свяжитесь с нашим оператором: @khurshedboboev",
                reply_markup=get_main_menu()
            )

        async def start_order_handler(message: Message, state: FSMContext):
            await message.answer("📍 Откуда забрать посылку?")
            await state.set_state(OrderForm.from_address)

        async def process_from_address_handler(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main_handler(message)
                await state.clear()
                return
                
            await state.update_data(from_address=message.text)
            await message.answer("📍 Куда доставить?")
            await state.set_state(OrderForm.to_address)

        async def process_to_address_handler(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main_handler(message)
                await state.clear()
                return
                
            await state.update_data(to_address=message.text)
            await message.answer("📞 Укажите номер телефона получателя:")
            await state.set_state(OrderForm.phone)

        async def process_phone_handler(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main_handler(message)
                await state.clear()
                return
                
            await state.update_data(phone=message.text)
            await message.answer("📦 Что за посылка? (Документы, еда, техника и т.д.)")
            await state.set_state(OrderForm.package_type)

        async def process_package_type_handler(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main_handler(message)
                await state.clear()
                return
                
            await state.update_data(package_type=message.text)
            await message.answer(
                "📸 Прикрепите фото посылки (или отправьте 'Нет' если фото нет):",
                reply_markup=get_back_to_menu_button()
            )
            await state.set_state(OrderForm.photo)

        # Регистрация обработчиков
        router.message(Command("start"))(start_handler)
        router.message(F.text == "🏠 Главное меню")(back_to_main_handler)
        router.message(F.text == "ℹ️ О нас")(about_us_handler)
        router.message(F.text == "🛵 Стать курьером")(become_courier_handler)
        router.message(F.text == "📦 Курьерские услуги")(start_order_handler)
        router.message(OrderForm.from_address)(process_from_address_handler)
        router.message(OrderForm.to_address)(process_to_address_handler)
        router.message(OrderForm.phone)(process_phone_handler)
        router.message(OrderForm.package_type)(process_package_type_handler)

        async def send_order_to_group(
            bot: Bot,
            group_id: int,
            order_id: int,
            user_data: dict,
            message: Message,
            button_text: str,
            callback_prefix: str
        ):
            """Универсальная функция для отправки заказа в группу"""
            order_text = (
                f"📦 Новый заказ #{order_id}\n\n"
                f"👤 Клиент: @{message.from_user.username or message.from_user.full_name}\n"
                f"📍 Откуда: {user_data['from_address']}\n"
                f"📍 Куда: {user_data['to_address']}\n"
                f"📞 Телефон: {user_data['phone']}\n"
                f"📦 Тип: {user_data['package_type']}"
            )

            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=button_text, callback_data=f"{callback_prefix}:{order_id}")]
            ])

            if message.content_type == ContentType.PHOTO:
                await bot.send_photo(
                    group_id,
                    photo=message.photo[-1].file_id,
                    caption=order_text,
                    reply_markup=markup
                )
            else:
                await bot.send_message(group_id, order_text, reply_markup=markup)

        # Объявляем функции-обработчики
        async def process_photo_handler(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main_handler(message)
                await state.clear()
                return
                
            user_data = await state.get_data()
            photo_file = None
            photo_file_id = None

            if message.content_type == ContentType.PHOTO:
                photo = message.photo[-1]
                photo_file_id = photo.file_id
                photo_file_obj = await bot.get_file(photo.file_id)
                file_bytes = await bot.download_file(photo_file_obj.file_path)
                photo_file = ContentFile(file_bytes.read(), name=f"order_{message.from_user.id}_{photo.file_id}.jpg")

            order_id = await create_order(
                user_id=message.from_user.id,
                username=message.from_user.username,
                from_address=user_data['from_address'],
                to_address=user_data['to_address'],
                phone=user_data['phone'],
                package_type=user_data['package_type'],
                photo=photo_file,
                photo_file_id=photo_file_id
            )

            await message.answer(
                f"✅ Ваш заказ #{order_id} принят. Ожидайте расчета стоимости.",
                reply_markup=get_main_menu()
            )

            await send_order_to_group(
                bot=bot,
                group_id=GROUP_ID,
                order_id=order_id,
                user_data=user_data,
                message=message,
                button_text="💰 Указать цену",
                callback_prefix="set_price"
            )

            await state.clear()

        async def request_price_input_handler(callback: CallbackQuery, state: FSMContext):
            order_id = int(callback.data.split(":")[1])
            await state.update_data(order_id=order_id)
            await state.set_state("waiting_for_price")
            
            await callback.message.answer(f"Введите стоимость доставки для заказа #{order_id}:")
            await callback.answer()

        async def process_price_input_handler(message: Message, state: FSMContext):
            try:
                price = float(message.text)
                if price <= 0:
                    raise ValueError("Цена должна быть положительной")
                
                state_data = await state.get_data()
                order_id = state_data.get('order_id')
                
                if not order_id:
                    await message.answer("❌ Ошибка: не удалось определить заказ.", reply_markup=get_main_menu())
                    return

                await set_order_price(order_id, price)
                order = await get_order_by_id(order_id)
                if not order:
                    await message.answer("❌ Заказ не найден.", reply_markup=get_main_menu())
                    return

                client_message = (
                    f"💰 Стоимость доставки: {price} сомони.\n\n"
                    f"⚠️ Отправитель гарантирует, что посылка не содержит запрещённых предметов.\n"
                    f"Подтвердите заказ:"
                )

                confirm_markup = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text=f"✅ Подтвердить заказ")]],
                    resize_keyboard=True
                )

                await bot.send_message(
                    order.user_id,
                    client_message,
                    reply_markup=confirm_markup
                )

                await message.answer(
                    f"✅ Цена {price} сомони установлена для заказа #{order_id}.\n"
                    f"Ожидаем подтверждения от клиента."
                )

                await state.clear()

            except ValueError as e:
                await message.answer(f"❌ Неверный формат цены: {str(e)}", reply_markup=get_main_menu())

        async def confirm_order_handler_handler(message: Message):
            payment_markup = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="💵 Наличные при получении")],
                    [KeyboardButton(text="📱 Перевод на карту или онлайн-кошелёк")]
                ],
                resize_keyboard=True
            )
            await message.answer("💳 Выберите способ оплаты:", reply_markup=payment_markup)

        async def online_payment_handler(message: Message):
            payment_text = (
                "💳 Реквизиты для оплаты:\n\n"
                f"Номер карты: `{PAYMENT_DETAILS['card_number']}`\n"
                f"Номер телефона: {PAYMENT_DETAILS['phone_number']}\n\n"
                "После оплаты, нажмите кнопку ниже и отправьте скриншот чека:"
            )
            
            receipt_markup = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📤 Отправить чек оплаты")]],
                resize_keyboard=True
            )
            await message.answer(payment_text, reply_markup=receipt_markup)

        async def request_receipt_handler(message: Message, state: FSMContext):
            await message.answer("Пожалуйста, отправьте фото или документ с чеком:", reply_markup=ReplyKeyboardRemove())
            await state.set_state(PaymentForm.waiting_for_receipt)

        async def cash_payment_handler(message: Message):
            try:
                order = await sync_to_async(Order.objects.filter(user_id=message.from_user.id).last)()
                
                if not order:
                    await message.answer("❌ Не найден ваш заказ. Начните заново.", reply_markup=get_main_menu())
                    return
                
                order.status = 'waiting_courier'
                await sync_to_async(order.save)()
                
                await send_order_to_group(
                    bot=bot,
                    group_id=COURIER_GROUP_ID,
                    order_id=order.id,
                    user_data={
                        'from_address': order.from_address,
                        'to_address': order.to_address,
                        'phone': order.phone,
                        'package_type': order.package_type
                    },
                    message=message,
                    button_text="✅ Принять заказ",
                    callback_prefix="courier_accept"
                )
                
                await message.answer(
                    "✅ Вы выбрали оплату наличными при получении.\n\n"
                    "Ваш заказ отправлен курьерам. Ожидайте, когда курьер примет заказ.",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            except Exception as e:
                print(f"Ошибка при обработке наличной оплаты: {e}")
                await message.answer(
                    "❌ Произошла ошибка при обработке заказа. Попробуйте еще раз.",
                    reply_markup=get_main_menu()
                )

        async def process_receipt_handler(message: Message, state: FSMContext):
            try:
                order = await sync_to_async(Order.objects.filter(user_id=message.from_user.id).last)()
                
                if not order:
                    await message.answer("❌ Не найден ваш заказ. Начните заново.", reply_markup=get_main_menu())
                    await state.clear()
                    return

                callback_data_confirm = f"confirm_payment:{message.from_user.id}:{order.id}"
                callback_data_reject = f"reject_payment:{message.from_user.id}:{order.id}"
                
                operator_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=callback_data_confirm),
                        InlineKeyboardButton(text="❌ Отклонить оплату", callback_data=callback_data_reject)
                    ]
                ])
                
                operator_text = (
                    f"Чек об оплате:\n"
                    f"Заказ #{order.id}\n"
                    f"Клиент: @{message.from_user.username or 'нет'}\n"
                    f"ID: {message.from_user.id}\n"
                    f"Имя: {message.from_user.full_name}"
                )
                
                if message.content_type == ContentType.PHOTO:
                    await bot.send_photo(
                        GROUP_ID,
                        photo=message.photo[-1].file_id,
                        caption=operator_text,
                        reply_markup=operator_markup
                    )
                else:
                    await bot.send_document(
                        GROUP_ID,
                        document=message.document.file_id,
                        caption=operator_text,
                        reply_markup=operator_markup
                    )
                
                await message.answer(
                    "Чек отправлен оператору на проверку. Ожидайте подтверждения.",
                    reply_markup=ReplyKeyboardRemove()
                )
                await state.clear()
                
            except Exception as e:
                print(f"Ошибка при обработке чека: {e}")
                await message.answer(
                    "Произошла ошибка при обработке чека. Попробуйте еще раз.",
                    reply_markup=ReplyKeyboardRemove()
                )
                await state.clear()

        # Регистрируем обработчики
        router.message(OrderForm.photo, F.content_type.in_({ContentType.PHOTO, ContentType.TEXT}))(process_photo_handler)
        router.callback_query(F.data.startswith("set_price:"))(request_price_input_handler)
        router.message(F.chat.id == GROUP_ID, F.text, StateFilter("waiting_for_price"))(process_price_input_handler)
        router.message(F.text == "✅ Подтвердить заказ")(confirm_order_handler_handler)
        router.message(F.text == "📱 Перевод на карту или онлайн-кошелёк")(online_payment_handler)
        router.message(F.text == "📤 Отправить чек оплаты")(request_receipt_handler)
        router.message(F.text == "💵 Наличные при получении")(cash_payment_handler)
        router.message(PaymentForm.waiting_for_receipt, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT}))(process_receipt_handler)

        # Добавляем новые константы
        COURIER_GROUP_ID = -1002648695686  # ID группы курьеров

        # Добавляем новые асинхронные методы для работы с БД
        @sync_to_async
        def assign_courier(order_id: int, courier_id: int, courier_username: str):
            order = Order.objects.get(id=order_id)
            order.courier_id = courier_id
            order.courier_link = f"https://t.me/{courier_username}" if courier_username else None
            order.status = 'assigned'
            order.save()
            return order

        @sync_to_async
        def update_order_status(order_id: int, status: str):
            order = Order.objects.get(id=order_id)
            order.status = status
            order.save()
            return order

        @sync_to_async
        def set_courier_message(order_id: int, message: str):
            order = Order.objects.get(id=order_id)
            order.courier_message = message
            order.save()
            return order

        @sync_to_async
        def set_delivery_message(order_id: int, message: str):
            order = Order.objects.get(id=order_id)
            order.delivery_message = message
            order.status = 'delivered'
            order.save()
            return order

        # Добавляем новые состояния
        class CourierStates(StatesGroup):
            waiting_for_courier_message = State()
            waiting_for_delivery_confirmation = State()
            waiting_for_delivery_message = State()
            waiting_for_client_confirmation = State()

        # Модифицируем обработчик подтверждения оплаты
        # Объявляем функции-обработчики
        async def handle_payment_confirmation_handler(callback: CallbackQuery):
            try:
                _, user_id, order_id = callback.data.split(":")
                user_id = int(user_id)
                order_id = int(order_id)
                
                order = await sync_to_async(Order.objects.get)(id=order_id)
                order.status = 'paid'
                await sync_to_async(order.save)()
                
                order_text = (
                    f"🚚 Новый заказ для доставки #{order.id}\n\n"
                    f"📍 Откуда: {order.from_address}\n"
                    f"📍 Куда: {order.to_address}\n"
                    f"📦 Тип: {order.package_type}\n"
                    f"💰 Сумма: {order.price} сомони\n"
                    f"📞 Телефон: {order.phone}"
                )
                
                accept_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Принять заказ", callback_data=f"courier_accept:{order.id}")]
                ])
                
                await bot.send_message(
                    COURIER_GROUP_ID,
                    order_text,
                    reply_markup=accept_markup
                )
                
                await callback.message.edit_reply_markup()
                await callback.answer("Оплата подтверждена, заказ отправлен курьерам")
                
                await bot.send_message(
                    user_id,
                    "✅ Оплата принята! Ваш заказ отправлен курьерам.\n"
                    "Ожидайте, когда курьер примет заказ.",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            except Exception as e:
                print(f"Ошибка при подтверждении оплаты: {e}")
                await callback.answer("❌ Произошла ошибка")

        async def courier_accept_order_handler(callback: CallbackQuery, state: FSMContext):
            try:
                order_id = int(callback.data.split(":")[1])
                courier = callback.from_user
                
                order = await get_order_by_id(order_id)
                if not order:
                    await callback.answer("❌ Заказ не найден")
                    return
                    
                if order.status != 'paid':
                    await callback.answer("❌ Заказ уже принят другим курьером")
                    return
                
                order = await assign_courier(
                    order_id=order_id,
                    courier_id=courier.id,
                    courier_username=courier.username
                )
                
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception as e:
                    print(f"Ошибка при редактировании сообщения: {e}")
                
                await callback.answer("✅ Вы приняли заказ")
                await send_order_to_courier(order)
                
                try:
                    await bot.send_message(
                        order.user_id,
                        f"🚚 Ваш заказ #{order.id} принят курьером.\n"
                        f"Связь с курьером: {order.courier_link or 'не указан'}\n\n"
                        "Курьер скоро свяжется с вами."
                    )
                except Exception as e:
                    print(f"Ошибка при уведомлении клиента: {e}")
                
            except Exception as e:
                print(f"Ошибка при принятии заказа курьером: {e}")
                await callback.answer("❌ Произошла ошибка при принятии заказа")

        async def courier_arrival_handler(callback: CallbackQuery, state: FSMContext):
            order_id = int(callback.data.split(":")[1])
            await state.update_data(order_id=order_id)
            await callback.message.answer(
                "📝 Напишите клиенту, через сколько времени вы прибудете (например: 'Буду через 15 минут'):",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(CourierStates.waiting_for_courier_message)
            await callback.answer()

        async def process_courier_message_handler(message: Message, state: FSMContext):
            try:
                state_data = await state.get_data()
                order_id = state_data['order_id']
                
                order = await set_courier_message(order_id, message.text)
                await update_order_status(order_id, 'in_progress')
                
                await bot.send_message(
                    order.user_id,
                    f"📦 Курьер в пути!\n\n"
                    f"Сообщение курьера: {message.text}\n\n"
                )
                
                await message.answer(
                    "Отлично! Клиент уведомлен. Когда доставите заказ, нажмите кнопку ниже:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="🚚 Подтвердить доставку",
                            callback_data=f"courier_delivered:{order_id}"
                        )
                    ]])
                )
                
            except Exception as e:
                print(f"Ошибка при обработке сообщения курьера: {e}")
                await message.answer("❌ Произошла ошибка", reply_markup=get_main_menu())
                await state.clear()

        async def courier_delivered_handler(callback: CallbackQuery, state: FSMContext):
            order_id = int(callback.data.split(":")[1])
            await state.update_data(order_id=order_id)
            await callback.message.answer(
                "📝 Напишите клиенту, где вы находитесь (например: 'Я у подъезда дома 5'):",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(CourierStates.waiting_for_delivery_message)
            await callback.answer()

        async def process_delivery_message_handler(message: Message, state: FSMContext):
            try:
                state_data = await state.get_data()
                order_id = state_data['order_id']
                
                order = await set_delivery_message(order_id, message.text)
                
                confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="✅ Подтвердить получение",
                        callback_data=f"client_confirm:{order.id}"
                    )
                ]])
                
                try:
                    await bot.send_message(
                        chat_id=order.user_id,
                        text=f"🚚 Курьер прибыл на место:\n\n"
                            f"Сообщение курьера: {message.text}\n\n"
                            "Пожалуйста, подтвердите получение:",
                        reply_markup=confirm_keyboard
                    )
                except Exception as e:
                    print(f"Не удалось уведомить клиента: {e}")
                    await message.answer(
                        "❌ Не удалось отправить уведомление клиенту. "
                        "Попросите его подтвердить получение вручную."
                    )
                    await state.clear()
                    return
                
                await message.answer(
                    "✅ Клиент уведомлен о вашем прибытии. Ожидайте подтверждения.",
                    reply_markup=get_main_menu()
                )
                
                await state.clear()
                
            except Exception as e:
                print(f"Ошибка при обработке сообщения о доставке: {e}")
                await message.answer(
                    "❌ Произошла ошибка при обработке подтверждения",
                    reply_markup=get_main_menu()
                )
                await state.clear()

        async def handle_client_confirmation_handler(callback: CallbackQuery):
            try:
                order_id = int(callback.data.split(":")[1])
                
                order = await sync_to_async(Order.objects.get)(id=order_id)
                order.status = 'delivered'
                await sync_to_async(order.save)()
                
                try:
                    await bot.send_message(
                        chat_id=order.courier_id,
                        text=f"✅ Клиент подтвердил получение заказа #{order.id}!\n"
                            "Спасибо за работу!"
                    )
                except Exception as e:
                    print(f"Не удалось уведомить курьера: {e}")
                
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.answer(
                    "✅ Получение подтверждено! Спасибо, что выбрали наш сервис!\n\n"
                    "Пожалуйста, оцените качество обслуживания:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⭐️ 1", callback_data=f"rate:1:{order_id}")],
                        [InlineKeyboardButton(text="⭐️ 2", callback_data=f"rate:2:{order_id}")],
                        [InlineKeyboardButton(text="⭐️ 3", callback_data=f"rate:3:{order_id}")],
                        [InlineKeyboardButton(text="⭐️ 4", callback_data=f"rate:4:{order_id}")],
                        [InlineKeyboardButton(text="⭐️ 5", callback_data=f"rate:5:{order_id}")]
                    ])
                )
                
                await callback.answer()
                
            except Exception as e:
                print(f"Ошибка при подтверждении получения: {e}")
                await callback.answer("❌ Произошла ошибка при подтверждении")

        async def process_rating_handler(callback: CallbackQuery, state: FSMContext):
            try:
                _, rating, order_id = callback.data.split(":")
                rating = int(rating)
                order_id = int(order_id)
                
                await sync_to_async(Order.objects.filter(id=order_id).update)(
                    client_score=rating
                )
                
                feedback_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📝 Оставить отзыв", callback_data=f"give_feedback:{order_id}"),
                        InlineKeyboardButton(text="🚫 Пропустить", callback_data=f"skip_feedback:{order_id}")
                    ]
                ])
                
                await callback.message.edit_text(
                    "Спасибо за оценку! Хотите оставить текстовый отзыв?",
                    reply_markup=feedback_markup
                )
                
                await state.update_data(order_id=order_id)
                await state.set_state(FeedbackStates.waiting_for_feedback_choice)
                await callback.answer()
                
            except Exception as e:
                print(f"Ошибка при обработке оценки: {e}")
                await callback.answer("❌ Произошла ошибка")

        async def request_feedback_handler(callback: CallbackQuery, state: FSMContext):
            try:
                await callback.message.edit_text(
                    "Пожалуйста, напишите ваш отзыв:",
                    reply_markup=None
                )
                await state.set_state(FeedbackStates.waiting_for_feedback_text)
                await callback.answer()
            except Exception as e:
                print(f"Ошибка при запросе отзыва: {e}")
                await callback.answer("❌ Произошла ошибка")

        async def skip_feedback_handler(callback: CallbackQuery, state: FSMContext):
            try:
                await callback.message.edit_text("Спасибо за вашу оценку!")
                await state.clear()
                await callback.answer()
            except Exception as e:
                print(f"Ошибка при пропуске отзыва: {e}")
                await callback.answer("❌ Произошла ошибка")

        async def save_feedback_text_handler(message: Message, state: FSMContext):
            try:
                state_data = await state.get_data()
                order_id = state_data['order_id']
                
                await sync_to_async(Order.objects.filter(id=order_id).update)(
                    client_feedback=message.text
                )
                
                await message.answer("Спасибо за ваш отзыв! Мы ценим ваше мнение.", reply_markup=get_main_menu())
                await state.clear()
                
            except Exception as e:
                print(f"Ошибка при сохранении отзыва: {e}")
                await message.answer("❌ Не удалось сохранить отзыв. Попробуйте позже.", reply_markup=get_main_menu())
                await state.clear()

        async def contact_operator_handler(message: Message):
            await message.answer(
                "Для связи с оператором напишите @zudrason_operator\n"
                "или позвоните по номеру +992123456789",
                reply_markup=ReplyKeyboardRemove()
            )

        async def retry_payment_handler(message: Message):
            await online_payment_handler(message)

        # Регистрируем обработчики
        router.callback_query(F.data.startswith("confirm_payment:"))(handle_payment_confirmation_handler)
        router.callback_query(F.data.startswith("courier_accept:"))(courier_accept_order_handler)
        router.callback_query(F.data.startswith("courier_arrival:"))(courier_arrival_handler)
        router.message(CourierStates.waiting_for_courier_message)(process_courier_message_handler)
        router.callback_query(F.data.startswith("courier_delivered:"))(courier_delivered_handler)
        router.message(CourierStates.waiting_for_delivery_message)(process_delivery_message_handler)
        router.callback_query(F.data.startswith("client_confirm:"))(handle_client_confirmation_handler)
        router.callback_query(F.data.startswith("rate:"))(process_rating_handler)
        router.callback_query(F.data.startswith("give_feedback:"), FeedbackStates.waiting_for_feedback_choice)(request_feedback_handler)
        router.callback_query(F.data.startswith("skip_feedback:"), FeedbackStates.waiting_for_feedback_choice)(skip_feedback_handler)
        router.message(FeedbackStates.waiting_for_feedback_text)(save_feedback_text_handler)
        router.message(F.text == "📞 Связаться с оператором")(contact_operator_handler)
        router.message(F.text == "🔄 Попробовать снова")(retry_payment_handler)

        async def main():
            """Основная асинхронная функция для запуска бота"""
            self.stdout.write(self.style.SUCCESS('Бот запускается...'))
            await dp.start_polling(bot)

        # Запуск бота
        asyncio.run(main())