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
from bs4 import BeautifulSoup
from config import BOT_TOKEN

# Log
logging.basicConfig(level=logging.INFO)

# Bot & Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Fayldan joylashuvlarni yuklaymiz
with open("locations.json", "r", encoding="utf-8") as f:
    locations = json.load(f)

PAGE_SIZE = 10

class LocationStates(StatesGroup):
    City = State()
    District = State()
    Street = State()
    House = State()
    Provider = State()

user_data = {}

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
        await msg.answer("Uy raqamini kiriting:", reply_markup=keyboard)
        return
    else:
        await msg.answer("Ko‘cha noto‘g‘ri. Qayta tanlang.")

    await state.update_data(page=page)
    keyboard = paginate_keyboard(street_list, "street", page)
    await msg.answer("Ko‘cha tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.House)
async def provider_buttons(msg: Message, state: FSMContext):
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
    city, district, street = data["city"], data["district"], data["street"]
    house = msg.text
    await state.update_data(house=house)

    await msg.answer("🔍 Provayderlar qidirilmoqda...")
    providers = []

    async with ClientSession() as session:
        try:
            async with session.get("https://internetbor.uz/api/v1/coverage-check/", params={"city": city, "district": district, "street": street, "house": house}) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    for p in res.get("providers", []):
                        if p.get("provider_id"):
                            providers.append((p.get("provider_name"), p.get("provider_id")))
        except Exception as e:
            await msg.answer("❌ Provayderlarni yuklashda xatolik.")
            return

    if not providers:
        await msg.answer("❌ Provayderlar topilmadi.")
        return

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[])
    for name, _id in providers:
        keyboard.keyboard.append([KeyboardButton(text=name)])
    keyboard.keyboard.append([KeyboardButton(text="🔙 Orqaga")])

    await state.set_state(LocationStates.Provider)
    user_data[msg.from_user.id] = {"providers": dict(providers)}
    await msg.answer("Provayderni tanlang:", reply_markup=keyboard)

@dp.message(LocationStates.Provider)
async def show_provider_tariffs(msg: Message, state: FSMContext):
    if msg.text == "🔙 Orqaga":
        await state.set_state(LocationStates.House)
        await msg.answer("Uy raqamini kiriting:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙 Orqaga")]]))
        return

    user = user_data.get(msg.from_user.id)
    if not user:
        await msg.answer("❌ Provayder ma’lumotlari yo‘q.")
        return

    prov_name = msg.text
    prov_id = user["providers"].get(prov_name)
    if not prov_id:
        await msg.answer("❌ Tanlangan provayder topilmadi.")
        return

    await msg.answer(f"<b>{prov_name}</b> tariflari:")

    async with ClientSession() as session:
        try:
            async with session.get(f"https://internetbor.uz/provider/{prov_id}") as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")

                all_cards = soup.select(".tariffCard")
                if not all_cards:
                    await msg.answer("❌ Tariflar topilmadi.")
                    return

                for card in all_cards:
                    name = card.select_one(".name")
                    price = card.select_one(".price")
                    speed = card.select_one(".dailySpeed__subtitle p")
                    night_speed = card.select_one(".nightlySpeed__subtitle p")
                    limit = card.select_one(".limit__subtitle")
                    tur = card.select_one(".type__subtitle")

                    tarif_text = f"<b>{name.text.strip()}</b>\n"
                    tarif_text += f"🌐 Tezlik: {speed.text.strip() if speed else '—'}\n"
                    tarif_text += f"🌙 Tungi: {night_speed.text.strip() if night_speed else '—'}\n"
                    tarif_text += f"💸 Narx: {price.text.strip() if price else '—'}\n"
                    tarif_text += f"📶 Limit: {limit.text.strip() if limit else '—'}\n"
                    tarif_text += f"📡 Turi: {tur.text.strip() if tur else '—'}"

                    await msg.answer(tarif_text)
        except Exception as e:
            await msg.answer("❌ Tariflarni yuklashda xatolik.")

# Run
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
