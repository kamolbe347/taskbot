import logging
import sqlite3
from datetime import date

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

API_TOKEN = "8518254628:AAFqTuf62AkL2RrbqQDKfy6FZV--R-lWndE"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ---------- DATABASE ----------
conn = sqlite3.connect("tasks.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks(
    user_id INTEGER,
    task TEXT,
    done INTEGER,
    day TEXT
)
""")
conn.commit()


# ---------- STATE ----------
class PlanState(StatesGroup):
    waiting_for_task = State()


# ---------- COMMANDS ----------
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Salom! /plan yozib vazifa qo‘sh")


# PLAN
@dp.message_handler(commands=['plan'])
async def plan(msg: types.Message):
    await PlanState.waiting_for_task.set()
    await msg.answer("Vazifani yozing:")


@dp.message_handler(state=PlanState.waiting_for_task)
async def save_task(msg: types.Message, state: FSMContext):
    today = str(date.today())
    cursor.execute(
        "INSERT INTO tasks VALUES(?,?,?,?)",
        (msg.from_user.id, msg.text, 0, today)
    )
    conn.commit()

    await msg.answer("Saqlandi ✅")
    await state.finish()


# TASK LIST
@dp.message_handler(commands=['tasks'])
async def tasks(msg: types.Message):
    today = str(date.today())
    cursor.execute(
        "SELECT rowid, task, done FROM tasks WHERE user_id=? AND day=?",
        (msg.from_user.id, today)
    )
    rows = cursor.fetchall()

    if not rows:
        await msg.answer("Bugun vazifa yo‘q")
        return

    text = ""
    for r in rows:
        status = "✅" if r[2] else "❌"
        text += f"{r[0]}. {r[1]} {status}\n"

    await msg.answer(text)


# DONE
@dp.message_handler(commands=['done'])
async def done(msg: types.Message):
    try:
        num = int(msg.get_args())
        cursor.execute("UPDATE tasks SET done=1 WHERE rowid=?", (num,))
        conn.commit()
        await msg.answer("Bajarildi ✔")
    except:
        await msg.answer("Misol: /done 1")


# CLEAR
@dp.message_handler(commands=['clear'])
async def clear(msg: types.Message):
    today = str(date.today())
    cursor.execute(
        "DELETE FROM tasks WHERE user_id=? AND day=?",
        (msg.from_user.id, today)
    )
    conn.commit()
    await msg.answer("Tozalandi 🧹")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
