import json
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiohttp import ClientSession
from config import BOT_TOKEN

# Log
logging.basicConfig(level=logging.INFO)

# Bot & Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Fayldan joylashuvlarni yuklaymiz
with open("locations.json", "r", encoding="utf-8") as f:
    locations = json.load(f)

# Sahifa hajmi
PAGE_SIZE = 10

# Holatlar
class LocationStates(StatesGroup):
    City = State()
    District = State()
    Street = State()
    House = State()

# 🔄 Sahifalash uchun yordamchi

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
    print(f"[START] {msg.from_user.full_name} ({msg.from_user.id}) botni boshladi.")
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
        print(f"[CITY] {msg.from_user.id} - Shahar tanlandi: {msg.text}")
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
        print(f"[DISTRICT] {msg.from_user.id} - Tuman tanlandi: {msg.text}")
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
        print(f"[STREET] {msg.from_user.id} - Ko‘cha tanlandi: {msg.text}")
        await state.update_data(street=msg.text)
        await state.set_state(LocationStates.House)
        # Only show back button
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="🔙 Orqaga")]
        ])
        await msg.answer("Iltimos, uy raqamini kiriting:", reply_markup=keyboard)
        return
    else:
        await msg.answer("Ko‘cha noto‘g‘ri. Qayta tanlang.")

    await state.update_data(page=page)
    keyboard = paginate_keyboard(street_list, "street", page)
    await msg.answer("Ko‘cha tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.House)
async def check_provider(msg: Message, state: FSMContext):
    if msg.text == "🔙 Orqaga":
        data = await state.get_data()
        city = data["city"]
        district = data["district"]
        streets = list(locations[city][district].keys())
        keyboard = paginate_keyboard(streets, "street", 0)
        await state.set_state(LocationStates.Street)
        print(f"[BACK] {msg.from_user.id} - Street bosqichiga qaytdi.")
        await msg.answer("Ko‘cha tanlang:", reply_markup=keyboard)
        return

    data = await state.get_data()
    city = data["city"]
    district = data["district"]
    street = data["street"]
    house = msg.text

    print(f"[HOUSE] {msg.from_user.id} - Uy raqami kiritildi: {house}")
    print(f"[API] So‘rov yuborilmoqda: {city}, {district}, {street}, {house}")

    await msg.answer("🔍 Provayderlar qidirilmoqda...")
    found_providers = []

    params = {
        "city": city,
        "district": district,
        "street": street,
        "house": house
    }

    async with ClientSession() as session:
        try:
            async with session.get("https://internetbor.uz/api/v1/coverage-check/", params=params) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    for provider in res.get("providers", []):
                        tariflar = "\n".join(
                            f" - {tarif.get('plan_name')} | {tarif.get('plan_speed')} | {tarif.get('plan_price')} so'm"
                            for tarif in provider.get("provider_best", [])
                        )
                        found_providers.append(f"📡 <b>{provider.get('provider_name')}</b>\n{tariflar}")
        except Exception as e:
            print(f"[ERROR] API chaqiruvda xatolik: {e}")
            await msg.answer("❌ Xatolik yuz berdi. Qayta urinib ko‘ring.")
            return

    if found_providers:
        print(f"[RESULT] {msg.from_user.id} uchun {len(found_providers)} ta provayder topildi.")
        await msg.answer("\n\n".join(found_providers))
    else:
        print(f"[RESULT] {msg.from_user.id} uchun provayder topilmadi.")
        await msg.answer("❌ Provayderlar topilmadi. Boshqa uy raqamini kiriting yoki 🔙 Orqaga qayting.")

# Run
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
