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
async def check_provider(msg: Message, state: FSMContext):
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
    city = data["city"]
    district = data["district"]
    street = data["street"]
    house = msg.text

    await msg.answer("🔍 Provayderlar qidirilmoqda...")

    params = {
        "city": city,
        "district": district,
        "street": street,
        "house": house
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

                for provider in providers:
                    name = provider.get("provider_name", "Nomaʼlum")
                    logo = provider.get("provider_logo", None)

                    tariflar = ""
                    for tarif in provider.get("provider_best", []):
                        nomi = tarif.get("plan_name", "—")
                        tezlik = tarif.get("plan_speed", "—")
                        narx = tarif.get("plan_price", "—")
                        tur = tarif.get("plan_type", "—")
                        tungi = tarif.get("night_speed", "—")
                        limit = tarif.get("plan_limit", "—")

                        tariflar += (
                            f"<b>{nomi}</b>\n"
                            f"🌐 Tezlik: <b>{tezlik}</b>\n"
                            f"🌙 Tungi: <i>{tungi}</i>\n"
                            f"💸 Narx: <code>{narx} so‘m/oy</code>\n"
                            f"📶 Limit: {limit}\n"
                            f"📡 Turi: {tur}\n\n"
                        )

                    header = f"<u>📡 <b>{name}</b></u>\n"
                    if logo:
                        header += f"🖼 <i>Logo:</i> <code>{logo}</code>\n\n"

                    await msg.answer(header + tariflar, parse_mode="HTML")

        except Exception as e:
            print(f"[ERROR] API chaqiruvda xatolik: {e}")
            await msg.answer("❌ Xatolik yuz berdi. Qayta urinib ko‘ring.")

# Run
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
