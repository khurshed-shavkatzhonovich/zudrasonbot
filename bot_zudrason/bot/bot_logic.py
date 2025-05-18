import os
import asyncio
from typing import Optional
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

from bot_zudrason.bot.models import Order

load_dotenv()

class BotHandler:
    def __init__(self):
        self.TOKEN = os.getenv("TOKEN")
        if not self.TOKEN:
            raise ValueError("TOKEN не найден в .env файле!")
        
        self.bot = Bot(token=self.TOKEN)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.router = Router()
        self.dp.include_router(self.router)
        
        # Константы
        self.GROUP_ID = -1002665268326  # ID группы оператора
        self.COURIER_GROUP_ID = -1002648695686  # ID группы курьеров
        self.PAYMENT_DETAILS = {
            "card_number": "1234567890118038",
            "phone_number": "+992501070777"
        }
        
        self._init_states()
        self._init_handlers()
    
    def _init_states(self):
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
        
        self.OrderForm = OrderForm
        self.PaymentForm = PaymentForm
        self.CourierStates = CourierStates
        self.FeedbackStates = FeedbackStates
    
    # Вспомогательные методы
    def get_main_menu(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📦 Курьерские услуги")],
                [KeyboardButton(text="ℹ️ О нас")],
                [KeyboardButton(text="🛵 Стать курьером")]
            ],
            resize_keyboard=True,
            is_persistent=True
        )

    def get_back_to_menu_button(self):
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
            resize_keyboard=True
        )

    async def send_order_to_group(self, group_id, order_id, user_data, message, button_text, callback_prefix):
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
            await self.bot.send_photo(
                group_id,
                photo=message.photo[-1].file_id,
                caption=order_text,
                reply_markup=markup
            )
        else:
            await self.bot.send_message(group_id, order_text, reply_markup=markup)

    async def send_order_to_courier(self, order):
        order_text = (
            f"🚚 Заказ #{order.id}\n"
            f"📍 Откуда: {order.from_address}\n"
            f"📍 Куда: {order.to_address}\n"
            f"📦 Тип: {order.package_type}\n"
            f"💰 Сумма: {order.price} сомони\n"
            f"📞 Телефон: {order.phone}"
        )
        
        arrival_button = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Сообщить время доставки клиенту",
                callback_data=f"courier_arrival:{order.id}"
            )
        ]])
        
        if order.photo and hasattr(order.photo, 'file_id'):
            try:
                await self.bot.send_photo(
                    chat_id=order.courier_id,
                    photo=order.photo.file_id,
                    caption=order_text,
                    reply_markup=arrival_button
                )
            except Exception as e:
                print(f"Ошибка при отправке фото: {e}")
                await self.bot.send_message(
                    chat_id=order.courier_id,
                    text=order_text,
                    reply_markup=arrival_button
                )
        else:
            await self.bot.send_message(
                chat_id=order.courier_id,
                text=order_text,
                reply_markup=arrival_button
            )

    # Методы для работы с БД
    @sync_to_async
    def create_order(self, user_id: int, username: str, from_address: str, to_address: str, 
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
    def get_order_by_id(self, order_id: int) -> Optional[Order]:
        try:
            return Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return None

    @sync_to_async
    def set_order_price(self, order_id: int, price: float) -> None:
        order = Order.objects.get(id=order_id)
        order.price = price
        order.save()

    @sync_to_async
    def confirm_order(self, order_id: int) -> None:
        order = Order.objects.get(id=order_id)
        order.status = 'confirmed'
        order.save()

    @sync_to_async
    def assign_courier(self, order_id: int, courier_id: int, courier_username: str):
        order = Order.objects.get(id=order_id)
        order.courier_id = courier_id
        order.courier_link = f"https://t.me/{courier_username}" if courier_username else None
        order.status = 'assigned'
        order.save()
        return order

    @sync_to_async
    def update_order_status(self, order_id: int, status: str):
        order = Order.objects.get(id=order_id)
        order.status = status
        order.save()
        return order

    @sync_to_async
    def set_courier_message(self, order_id: int, message: str):
        order = Order.objects.get(id=order_id)
        order.courier_message = message
        order.save()
        return order

    @sync_to_async
    def set_delivery_message(self, order_id: int, message: str):
        order = Order.objects.get(id=order_id)
        order.delivery_message = message
        order.status = 'delivered'
        order.save()
        return order

    def _init_handlers(self):
        # Основные команды
        @self.router.message(Command("start"))
        async def start(message: Message):
            await message.answer(
                "🚀 Добро пожаловать в Zudrason! 📦\n"
                "Мы доставляем еду, лекарства, посылки и всё, что вам нужно.\n"
                "Выберите категорию, чтобы начать!",
                reply_markup=self.get_main_menu()
            )

        @self.router.message(F.text == "🏠 Главное меню")
        async def back_to_main(message: Message):
            await start(message)

        # Информационные команды
        @self.router.message(F.text == "ℹ️ О нас")
        async def about_us(message: Message):
            await message.answer(
                """🚀 Zudrason — это современный сервис курьерской доставки.
                Мы работаем, чтобы ваши посылки доходили быстро и безопасно!""",
                reply_markup=self.get_main_menu()
            )

        @self.router.message(F.text == "🛵 Стать курьером")
        async def become_courier(message: Message):
            await message.answer(
                "Свяжитесь с нашим оператором: @khurshedboboev",
                reply_markup=self.get_main_menu()
            )

        # Оформление заказа
        @self.router.message(F.text == "📦 Курьерские услуги")
        async def start_order(message: Message, state: FSMContext):
            await message.answer("📍 Откуда забрать посылку?")
            await state.set_state(self.OrderForm.from_address)

        @self.router.message(self.OrderForm.from_address)
        async def process_from_address(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main(message)
                await state.clear()
                return
                
            await state.update_data(from_address=message.text)
            await message.answer("📍 Куда доставить?")
            await state.set_state(self.OrderForm.to_address)

        # ... (добавьте все остальные обработчики аналогичным образом)

        @self.router.message(self.OrderForm.to_address)
        async def process_to_address(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main(message)
                await state.clear()
                return
                
            await state.update_data(to_address=message.text)
            await message.answer(
                "📞 Укажите номер телефона получателя:"
            )
            await state.set_state(self.OrderForm.phone)

        @self.router.message(self.OrderForm.phone)
        async def process_phone(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main(message)
                await state.clear()
                return
                
            await state.update_data(phone=message.text)
            await message.answer(
                "📦 Что за посылка? (Документы, еда, техника и т.д.)"
            )
            await state.set_state(self.OrderForm.package_type)

        @self.router.message(self.OrderForm.package_type)
        async def process_package_type(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main(message)
                await state.clear()
                return
                
            await state.update_data(package_type=message.text)
            await message.answer(
                "📸 Прикрепите фото посылки (или отправьте 'Нет' если фото нет):",
                reply_markup=self.get_back_to_menu_button()
            )
            await state.set_state(self.OrderForm.photo)

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

        # Обработка фото заказа
        @self.router.message(self.OrderForm.photo, F.content_type.in_({ContentType.PHOTO, ContentType.TEXT}))
        async def process_photo(message: Message, state: FSMContext):
            if message.text == "🏠 Главное меню":
                await back_to_main(message)
                await state.clear()
                return
                
            user_data = await state.get_data()
            photo_file = None
            photo_file_id = None

            if message.content_type == ContentType.PHOTO:
                photo = message.photo[-1]
                photo_file_id = photo.file_id
                photo_file_obj = await self.bot.get_file(photo.file_id)
                file_bytes = await self.bot.download_file(photo_file_obj.file_path)
                photo_file = ContentFile(file_bytes.read(), name=f"order_{message.from_user.id}_{photo.file_id}.jpg")

            order_id = await self.create_order(
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
                reply_markup=self.get_main_menu()
            )

            await self.send_order_to_group(
                group_id=self.GROUP_ID,
                order_id=order_id,
                user_data=user_data,
                message=message,
                button_text="💰 Указать цену",
                callback_prefix="set_price"
            )

            await state.clear()

        # ... (продолжите перенос всех обработчиков)

        @self.router.callback_query(F.data.startswith("set_price:"))
        async def request_price_input(callback: CallbackQuery, state: FSMContext):
            order_id = int(callback.data.split(":")[1])
            await state.update_data(order_id=order_id)
            await state.set_state("waiting_for_price")
            
            await callback.message.answer(
                f"Введите стоимость доставки для заказа #{order_id}:"
            )
            await callback.answer()

        @self.router.message(F.chat.id == self.GROUP_ID, F.text, StateFilter("waiting_for_price"))
        async def process_price_input(message: Message, state: FSMContext):
            try:
                price = float(message.text)
                if price <= 0:
                    raise ValueError("Цена должна быть положительной",
                reply_markup=self.get_main_menu())
                
                state_data = await state.get_data()
                order_id = state_data.get('order_id')
                
                if not order_id:
                    await message.answer("❌ Ошибка: не удалось определить заказ.",
                reply_markup=self.get_main_menu())
                    return

                await self.set_order_price(order_id, price)
                order = await self.get_order_by_id(order_id)
                if not order:
                    await message.answer("❌ Заказ не найден.",
                reply_markup=self.get_main_menu())
                    return

                client_message = (
                    f"💰 Стоимость доставки: {price} сомони.\n\n"
                    f"⚠️ Отправитель гарантирует, что посылка не содержит запрещённых предметов.\n"
                    f"Подтвердите заказ:")

                confirm_markup = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text=f"✅ Подтвердить заказ")]],
                    resize_keyboard=True
                )

                await self.bot.send_message(
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
                await message.answer(f"❌ Неверный формат цены: {str(e)}",
                reply_markup=self.get_main_menu())

        @self.router.message(F.text == "✅ Подтвердить заказ")
        async def confirm_order_handler(message: Message):
            # Здесь должна быть логика обработки подтверждения заказа клиентом
            payment_markup = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="💵 Наличные при получении")],
                    [KeyboardButton(text="📱 Перевод на карту или онлайн-кошелёк")]
                ],
                resize_keyboard=True
            )

            await message.answer(
                "💳 Выберите способ оплаты:",
                reply_markup=payment_markup
            )

        class PaymentForm(StatesGroup):
            waiting_for_receipt = State()
            confirm_payment = State()

        # Добавляем эти константы в начало файла
        PAYMENT_DETAILS = {
            "card_number": "1234567890118038",
            "phone_number": "+992501070777"
        }

        @self.router.message(F.text == "📱 Перевод на карту или онлайн-кошелёк")
        async def online_payment(message: Message):
            """Обработка выбора онлайн оплаты"""
            # Отправляем реквизиты и QR-код (замените на реальный файл)
            payment_text = (
                "💳 Реквизиты для оплаты:\n\n"
                f"Номер карты: `{PAYMENT_DETAILS['card_number']}`\n"
                f"Номер телефона: {PAYMENT_DETAILS['phone_number']}\n\n"
                "После оплаты, нажмите кнопку ниже и отправьте скриншот чека:"
            )
            
            # Создаем кнопку для отправки чека
            receipt_markup = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📤 Отправить чек оплаты")]],
                resize_keyboard=True
            )
            
            # Отправляем текст с реквизитами
            await message.answer(payment_text, reply_markup=receipt_markup)
            
            # Здесь должна быть отправка реального QR-кода
            # await message.answer_photo(photo=open('qr_code.jpg', 'rb'))
            
            # Устанавливаем состояние ожидания чека

        @self.router.message(F.text == "📤 Отправить чек оплаты")
        async def request_receipt(message: Message, state: FSMContext):
            """Запрос чека об оплате"""
            await message.answer("Пожалуйста, отправьте фото или документ с чеком:", reply_markup=ReplyKeyboardRemove())
            await state.set_state(PaymentForm.waiting_for_receipt)

        @self.router.message(F.text == "💵 Наличные при получении")
        async def cash_payment(message: Message):
            """Обработка выбора наличной оплаты"""
            try:
                # Получаем последний заказ пользователя
                order = await sync_to_async(
                    Order.objects.filter(user_id=message.from_user.id).last
                )()
                
                if not order:
                    await message.answer("❌ Не найден ваш заказ. Начните заново.",
                        reply_markup=self.get_main_menu())
                    return
                
                # Обновляем статус заказа
                order.status = 'waiting_courier'
                await sync_to_async(order.save)()
                
                # Отправляем заказ в группу курьеров
                await send_order_to_group(
                    bot=self.bot,
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
                    reply_markup=self.get_main_menu()
                )
            
            # Здесь можно добавить логику уведомления оператора

        @self.router.message(PaymentForm.waiting_for_receipt, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT}))
        async def process_receipt(message: Message, state: FSMContext):
            """Обработка полученного чека"""
            try:
                # Получаем последний заказ пользователя
                order = await sync_to_async(
                    Order.objects.filter(user_id=message.from_user.id).last
                )()
                
                if not order:
                    await message.answer("❌ Не найден ваш заказ. Начните заново.",
                reply_markup=self.get_main_menu())
                    await state.clear()
                    return

                # Формируем callback_data с user_id и order_id
                callback_data_confirm = f"confirm_payment:{message.from_user.id}:{order.id}"
                callback_data_reject = f"reject_payment:{message.from_user.id}:{order.id}"
                
                # Создаем кнопки для оператора
                operator_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить оплату", 
                            callback_data=callback_data_confirm
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить оплату", 
                            callback_data=callback_data_reject
                        )
                    ]
                ])
                
                # Формируем текст сообщения для оператора
                operator_text = (
                    f"Чек об оплате:\n"
                    f"Заказ #{order.id}\n"
                    f"Клиент: @{message.from_user.username or 'нет'}\n"
                    f"ID: {message.from_user.id}\n"
                    f"Имя: {message.from_user.full_name}"
                )
                
                # Отправляем чек оператору
                if message.content_type == ContentType.PHOTO:
                    await self.bot.send_photo(
                        self.GROUP_ID,
                        photo=message.photo[-1].file_id,
                        caption=operator_text,
                        reply_markup=operator_markup
                    )
                else:
                    await self.bot.send_document(
                        self.GROUP_ID,
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
        @self.router.callback_query(F.data.startswith("confirm_payment:"))
        async def handle_payment_confirmation(callback: CallbackQuery):
            try:
                _, user_id, order_id = callback.data.split(":")
                user_id = int(user_id)
                order_id = int(order_id)
                
                order = await sync_to_async(Order.objects.get)(id=order_id)
                order.status = 'paid'
                await sync_to_async(order.save)()
                # Отправляем заказ в группу курьеров
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
                
                await self.bot.send_message(
                    COURIER_GROUP_ID,
                    order_text,
                    reply_markup=accept_markup
                )
                
                await callback.message.edit_reply_markup()
                await callback.answer("Оплата подтверждена, заказ отправлен курьерам")
                
                await self.bot.send_message(
                    user_id,
                    "✅ Оплата принята! Ваш заказ отправлен курьерам.\n"
                    "Ожидайте, когда курьер примет заказ.",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            except Exception as e:
                print(f"Ошибка при подтверждении оплаты: {e}")
                await callback.answer("❌ Произошла ошибка")

                # Отправляем заказ в группу курьеров
        async def send_order_to_courier(order: Order):
            """Отправляет полную информацию о заказе курьеру"""
            order_text = (
                f"🚚 Заказ #{order.id}\n"
                f"📍 Откуда: {order.from_address}\n"
                f"📍 Куда: {order.to_address}\n"
                f"📦 Тип: {order.package_type}\n"
                f"💰 Сумма: {order.price} сомони\n"
                f"📞 Телефон: {order.phone}"
            )
            
            # Создаем кнопку для подтверждения прибытия
            arrival_button = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="📝 Сообщить время доставки клиенту",
                    callback_data=f"courier_arrival:{order.id}"
                )
            ]])
            
            # Если есть фото - отправляем с фото (используем file_id если он сохранен)
            if order.photo and hasattr(order.photo, 'file_id'):
                try:
                    await self.bot.send_photo(
                        chat_id=order.courier_id,
                        photo=order.photo.file_id,
                        caption=order_text,
                        reply_markup=arrival_button
                    )
                except Exception as e:
                    print(f"Ошибка при отправке фото: {e}")
                    # Если не удалось отправить фото, отправляем только текст
                    await self.bot.send_message(
                        chat_id=order.courier_id,
                        text=order_text,
                        reply_markup=arrival_button
                    )
            else:
                await self.bot.send_message(
                    chat_id=order.courier_id,
                    text=order_text,
                    reply_markup=arrival_button
                )

        # ======================
        # ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ
        # ======================

        @self.router.callback_query(F.data.startswith("courier_accept:"))
        async def courier_accept_order(callback: CallbackQuery, state: FSMContext):
            try:
                order_id = int(callback.data.split(":")[1])
                courier = callback.from_user
                
                # Получаем заказ
                order = await self.get_order_by_id(order_id)
                if not order:
                    await callback.answer("❌ Заказ не найден")
                    return
                    
                # Проверяем, не принят ли уже заказ другим курьером
                if order.status != 'paid':
                    await callback.answer("❌ Заказ уже принят другим курьером")
                    return
                
                # Сохраняем курьера в заказе
                order = await assign_courier(
                    order_id=order_id,
                    courier_id=courier.id,
                    courier_username=courier.username
                )
                
                # Удаляем кнопку "Принять" из сообщения в группе
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception as e:
                    print(f"Ошибка при редактировании сообщения: {e}")
                
                await callback.answer("✅ Вы приняли заказ")
                
                # Отправляем полную информацию курьеру
                await send_order_to_courier(order)
                
                # Уведомляем клиента
                try:
                    await self.bot.send_message(
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

        @self.router.callback_query(F.data.startswith("courier_arrival:"))
        async def courier_arrival(callback: CallbackQuery, state: FSMContext):
            order_id = int(callback.data.split(":")[1])
            await state.update_data(order_id=order_id)
            await callback.message.answer(
                "📝 Напишите клиенту, через сколько времени вы прибудете (например: 'Буду через 15 минут'):",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(CourierStates.waiting_for_courier_message)
            await callback.answer()

        @self.router.message(CourierStates.waiting_for_courier_message)
        async def process_courier_message(message: Message, state: FSMContext):
            try:
                state_data = await state.get_data()
                order_id = state_data['order_id']
                
                # Обновляем заказ
                order = await set_courier_message(order_id, message.text)
                await update_order_status(order_id, 'in_progress')
                
                # Отправляем сообщение клиенту
                await self.bot.send_message(
                    order.user_id,
                    f"📦 Курьер в пути!\n\n"
                    f"Сообщение курьера: {message.text}\n\n"
                )
                
                # Отправляем кнопку курьеру для подтверждения доставки
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
                await message.answer("❌ Произошла ошибка", reply_markup=self.get_main_menu())
                await state.clear()

        @self.router.callback_query(F.data.startswith("courier_delivered:"))
        async def courier_delivered(callback: CallbackQuery, state: FSMContext):
            order_id = int(callback.data.split(":")[1])
            await state.update_data(order_id=order_id)
            await callback.message.answer(
                "📝 Напишите клиенту, где вы находитесь (например: 'Я у подъезда дома 5'):",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(CourierStates.waiting_for_delivery_message)
            await callback.answer()

        @self.router.message(CourierStates.waiting_for_delivery_message)
        async def process_delivery_message(message: Message, state: FSMContext):
            try:
                state_data = await state.get_data()
                order_id = state_data['order_id']
                
                # Обновляем заказ (асинхронно)
                order = await set_delivery_message(order_id, message.text)
                
                # Создаем клавиатуру для подтверждения
                confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="✅ Подтвердить получение",
                        callback_data=f"client_confirm:{order.id}"
                    )
                ]])
                
                # Отправляем сообщение клиенту
                try:
                    await self.bot.send_message(
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
                    reply_markup=self.get_main_menu()
                )
                
                await state.clear()
                
            except Exception as e:
                print(f"Ошибка при обработке сообщения о доставке: {e}")
                await message.answer(
                    "❌ Произошла ошибка при обработке подтверждения",
                    reply_markup=self.get_main_menu()
                )
                await state.clear()

        @self.router.callback_query(F.data.startswith("client_confirm:"))
        async def handle_client_confirmation(callback: CallbackQuery):
            try:
                order_id = int(callback.data.split(":")[1])
                
                # Получаем и обновляем заказ
                order = await sync_to_async(Order.objects.get)(id=order_id)
                order.status = 'delivered'
                await sync_to_async(order.save)()
                
                # Уведомляем курьера
                try:
                    await self.bot.send_message(
                        chat_id=order.courier_id,
                        text=f"✅ Клиент подтвердил получение заказа #{order.id}!\n"
                            "Спасибо за работу!"
                    )
                except Exception as e:
                    print(f"Не удалось уведомить курьера: {e}")
                
                # Обновляем сообщение у клиента
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


        @self.router.callback_query(F.data.startswith("rate:"))
        async def process_rating(callback: CallbackQuery, state: FSMContext):
            try:
                _, rating, order_id = callback.data.split(":")
                rating = int(rating)
                order_id = int(order_id)
                
                # Сохраняем оценку
                await sync_to_async(Order.objects.filter(id=order_id).update)(
                    client_score=rating
                )
                
                # Предлагаем оставить отзыв
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
                
                # Сохраняем order_id в состоянии
                await state.update_data(order_id=order_id)
                await state.set_state(self.FeedbackStates.waiting_for_feedback_choice)
                
                await callback.answer()
                
            except Exception as e:
                print(f"Ошибка при обработке оценки: {e}")
                await callback.answer("❌ Произошла ошибка")

        @self.router.callback_query(F.data.startswith("give_feedback:"), self.FeedbackStates.waiting_for_feedback_choice)
        async def request_feedback(callback: CallbackQuery, state: FSMContext):
            try:
                await callback.message.edit_text(
                    "Пожалуйста, напишите ваш отзыв:",
                    reply_markup=None  # Убираем клавиатуру
                )
                await state.set_state(self.FeedbackStates.waiting_for_feedback_text)
                await callback.answer()
            except Exception as e:
                print(f"Ошибка при запросе отзыва: {e}")
                await callback.answer("❌ Произошла ошибка")

        @self.router.callback_query(F.data.startswith("skip_feedback:"), self.FeedbackStates.waiting_for_feedback_choice)
        async def skip_feedback(callback: CallbackQuery, state: FSMContext):
            try:
                await callback.message.edit_text("Спасибо за вашу оценку!")
                await state.clear()
                await callback.answer()
            except Exception as e:
                print(f"Ошибка при пропуске отзыва: {e}")
                await callback.answer("❌ Произошла ошибка")

        @self.router.message(self.FeedbackStates.waiting_for_feedback_text)
        async def save_feedback_text(message: Message, state: FSMContext):
            try:
                state_data = await state.get_data()
                order_id = state_data['order_id']
                
                # Сохраняем отзыв
                await sync_to_async(Order.objects.filter(id=order_id).update)(
                    client_feedback=message.text
                )
                
                await message.answer("Спасибо за ваш отзыв! Мы ценим ваше мнение.", reply_markup=self.get_main_menu())
                await state.clear()
                
            except Exception as e:
                print(f"Ошибка при сохранении отзыва: {e}")
                await message.answer("❌ Не удалось сохранить отзыв. Попробуйте позже.", reply_markup=self.get_main_menu())
                await state.clear()

        @self.router.message(F.text == "📞 Связаться с оператором")
        async def contact_operator(message: Message):
            """Обработка запроса связи с оператором"""
            await message.answer(
                "Для связи с оператором напишите @zudrason_operator\n"
                "или позвоните по номеру +992123456789",
                reply_markup=ReplyKeyboardRemove()
            )

        @self.router.message(F.text == "🔄 Попробовать снова")
        async def retry_payment(message: Message):
            """Повторная попытка оплаты"""
            await online_payment(message)

    async def start_polling(self):
        await self.dp.start_polling(self.bot)