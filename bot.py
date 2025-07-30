import json
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiohttp import ClientSession
from config import BOT_TOKEN

# Log
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

with open("locations.json", "r", encoding="utf-8") as f:
    locations = json.load(f)

PAGE_SIZE = 10

tg_username = "@sarkor_ceo"
telephone_number = "+998909228887"

class LocationStates(StatesGroup):
    City = State()
    District = State()
    Street = State()
    House = State()
    Provider = State()

def paginate_keyboard(items, state_key, page):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = items[start:end]

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[])
    for item in page_items:
        keyboard.keyboard.append([KeyboardButton(text=item)])

    navigation = []
    if page > 0:
        navigation.append(KeyboardButton(text="⏮️ Oldingi"))
    if end < len(items):
        navigation.append(KeyboardButton(text="⏭️ Keyingi"))

    if navigation:
        keyboard.keyboard.append(navigation)

    if state_key != "city":
        keyboard.keyboard.append([KeyboardButton(text="🔙 Orqaga")])

    return keyboard

@dp.message(F.text == "/start")
async def start(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(LocationStates.City)
    await state.update_data(page=0)
    keyboard = paginate_keyboard(list(locations.keys()), "city", 0)
    await msg.answer("Shaharni tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.City)
async def choose_district(msg: Message, state: FSMContext):
    data = await state.get_data()
    city_list = list(locations.keys())
    page = data.get("page", 0)

    if msg.text == "⏭️ Keyingi":
        page += 1
    elif msg.text == "⏮️ Oldingi":
        page -= 1
    elif msg.text in locations:
        await state.update_data(city=msg.text, page=0)
        await state.set_state(LocationStates.District)
        districts = list(locations[msg.text].keys())
        keyboard = paginate_keyboard(districts, "district", 0)
        await msg.answer("Tuman tanlang:", reply_markup=keyboard)
        return
    else:
        await msg.answer("Shahar noto‘g‘ri. Qayta tanlang.")

    await state.update_data(page=page)
    keyboard = paginate_keyboard(city_list, "city", page)
    await msg.answer("Shaharni tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.District)
async def choose_street(msg: Message, state: FSMContext):
    data = await state.get_data()
    city = data["city"]
    district_list = list(locations[city].keys())
    page = data.get("page", 0)

    if msg.text == "🔙 Orqaga":
        await state.set_state(LocationStates.City)
        keyboard = paginate_keyboard(list(locations.keys()), "city", 0)
        await msg.answer("Shaharni tanlang:", reply_markup=keyboard)
        return
    elif msg.text == "⏭️ Keyingi":
        page += 1
    elif msg.text == "⏮️ Oldingi":
        page -= 1
    elif msg.text in locations[city]:
        await state.update_data(district=msg.text, page=0)
        await state.set_state(LocationStates.Street)
        streets = list(locations[city][msg.text].keys())
        keyboard = paginate_keyboard(streets, "street", 0)
        await msg.answer("Ko‘cha tanlang:", reply_markup=keyboard)
        return
    else:
        await msg.answer("Tuman noto‘g‘ri. Qayta tanlang.")

    await state.update_data(page=page)
    keyboard = paginate_keyboard(district_list, "district", page)
    await msg.answer("Tuman tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.Street)
async def choose_house(msg: Message, state: FSMContext):
    data = await state.get_data()
    city = data["city"]
    district = data["district"]
    street_list = list(locations[city][district].keys())
    page = data.get("page", 0)

    if msg.text == "🔙 Orqaga":
        await state.set_state(LocationStates.District)
        keyboard = paginate_keyboard(list(locations[city].keys()), "district", 0)
        await msg.answer("Tuman tanlang:", reply_markup=keyboard)
        return
    elif msg.text == "⏭️ Keyingi":
        page += 1
    elif msg.text == "⏮️ Oldingi":
        page -= 1
    elif msg.text in locations[city][district]:
        await state.update_data(street=msg.text)
        await state.set_state(LocationStates.House)
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙 Orqaga")]])
        await msg.answer("Iltimos, uy raqamini kiriting:", reply_markup=keyboard)
        return
    else:
        await msg.answer("Ko‘cha noto‘g‘ri. Qayta tanlang.")

    await state.update_data(page=page)
    keyboard = paginate_keyboard(street_list, "street", page)
    await msg.answer("Ko‘cha tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.House)
async def list_providers(msg: Message, state: FSMContext):
    if msg.text == "🔙 Orqaga":
        data = await state.get_data()
        city = data["city"]
        district = data["district"]
        streets = list(locations[city][district].keys())
        keyboard = paginate_keyboard(streets, "street", 0)
        await state.set_state(LocationStates.Street)
        await msg.answer("Ko‘cha tanlang:", reply_markup=keyboard)
        return

    data = await state.get_data()
    await state.update_data(house=msg.text)
    await msg.answer("🔍 Provayderlar qidirilmoqda...")

    params = {
        "city": data["city"],
        "district": data["district"],
        "street": data["street"],
        "house": msg.text
    }

    async with ClientSession() as session:
        try:
            async with session.get("https://internetbor.uz/api/v1/coverage-check/", params=params) as resp:
                if resp.status != 200:
                    await msg.answer("❌ API javobida xatolik. Qayta urinib ko‘ring.")
                    return
                res = await resp.json()
                providers = res.get("providers", [])
                if not providers:
                    await msg.answer("❌ Hech qanday provayder topilmadi.")
                    return

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=prov.get("provider_name", "Nomaʼlum"), callback_data=f"prov_{i}")]
                        for i, prov in enumerate(providers)
                    ] + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_house")]]
                )
                await state.update_data(provider_data=providers)
                await state.set_state(LocationStates.Provider)
                await msg.answer("📡 Provayderni tanlang:", reply_markup=keyboard)

        except Exception as e:
            print(f"[ERROR] {e}")
            await msg.answer("❌ Xatolik yuz berdi. Qayta urinib ko‘ring.")

@dp.callback_query(LocationStates.Provider, F.data.startswith("prov_"))
async def show_tariffs(call: CallbackQuery, state: FSMContext):
    await call.answer()
    idx = int(call.data.split("_")[1])
    data = await state.get_data()
    provider = data["provider_data"][idx]

    name = provider.get("provider_name", "Nomaʼlum")
    tariflar = ""
    for tarif in provider.get("provider_best", []):
        tariflar += (
            f"<b>{tarif.get('plan_name')}</b>\n"
            f"🌐 Tezlik: {tarif.get('plan_speed')}\n"
            f"💸 Narx: {tarif.get('plan_price')} so‘m\n"
            f"📶 Limit: {tarif.get('plan_limit')}\n"
            f"🌙 Tungi: {tarif.get('night_speed')}\n"
            f"📡 Turi: {tarif.get('plan_type')}\n\n"
            f"<b>📡 {name}</b>\n\n{tariflar}<b>📞 Aloqa:</b> {telephone_number}"

        )

    markup = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✉️ Telegram orqali", url=f"https://t.me/{tg_username.lstrip('@')}")
        ],
        [
            InlineKeyboardButton(text="🔙 Provayderlar", callback_data="back_providers")
        ]
    ]
)

    await call.message.edit_text(f"<b>📡 {name}</b>\n\n{tariflar}", reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "back_providers")
async def back_to_providers(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    providers = data.get("provider_data", [])
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=prov.get("provider_name", "Nomaʼlum"), callback_data=f"prov_{i}")]
            for i, prov in enumerate(providers)
        ] + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_house")]]
    )
    await call.message.edit_text("📡 Provayderni tanlang:", reply_markup=keyboard)

@dp.callback_query(F.data == "back_house")
async def back_to_house(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    city, district, street = data["city"], data["district"], data["street"]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙 Orqaga")]])
    await state.set_state(LocationStates.House)
    await call.message.answer("Iltimos, uy raqamini kiriting:", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())