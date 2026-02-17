import logging
import sqlite3
from datetime import date
from datetime import datetime, timedelta
import asyncio



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

# tasks table
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task TEXT,
    done INTEGER,
    day TEXT,
    task_num INTEGER
)
""")

# streak table (NEW)
cursor.execute("""
CREATE TABLE IF NOT EXISTS streaks(
    user_id INTEGER PRIMARY KEY,
    last_day TEXT,
    streak INTEGER
)
""")

#reminder table
cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    day TEXT,
    task_num INTEGER,
    remind_time TEXT,
    sent INTEGER
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

    cursor.execute( "SELECT COUNT(*) FROM tasks WHERE user_id=? AND day=?", (msg.from_user.id, today))
    count = cursor.fetchone()[0] + 1

    cursor.execute("INSERT INTO tasks(user_id, task, done, day, task_num) VALUES(?,?,?,?,?)", (msg.from_user.id, msg.text, 0, today, count))
    conn.commit()


    await msg.answer("Saqlandi ✅")
    await state.finish()
    


# TASK LIST
@dp.message_handler(commands=['tasks'])
async def tasks(msg: types.Message):
    today = str(date.today())
    cursor.execute("SELECT task_num, task, done FROM tasks WHERE user_id=? AND day=? ORDER BY task_num", (msg.from_user.id, today))

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
        today = str(date.today())
        cursor.execute("UPDATE tasks SET done=1 WHERE user_id=? AND day=? AND task_num=?", (msg.from_user.id, today, num))
        conn.commit()
        await msg.answer("Bajarildi ✔")
    except:
        await msg.answer("Misol: /done 1")


# CLEAR
@dp.message_handler(commands=['clear'])
async def clear(msg: types.Message):
    today = str(date.today())
    cursor.execute("DELETE FROM tasks WHERE user_id=? AND day=?", (msg.from_user.id, today))
    conn.commit()
    await msg.answer("Tozalandi 🧹")


#----Help/Manual-----

@dp.message_handler(commands=['help'])
async def help_cmd(msg: types.Message):
    await msg.answer(
"""
/plan — yangi vazifa qo‘shish
/tasks — bugungi vazifalar
/done N — vazifani bajarildi deb belgilash
/delete N — vazifani o‘chirish
/remind N HH:MM — eslatma qo‘shish
/report — bugungi hisobot
/stat — umumiy statistika
/streak — ketma-ket kunlar
/clear — bugungi ro‘yxatni tozalash
/help — yordam"""
)


#---------Removing specific tasks----------------

@dp.message_handler(commands=['delete'])
async def delete_task(msg: types.Message):
    try:
        num = int(msg.get_args())
        today = str(date.today())

        cursor.execute(
            "DELETE FROM tasks WHERE user_id=? AND day=? AND task_num=?",
            (msg.from_user.id, today, num)
        )
        conn.commit()

        # re-number remaining tasks
        cursor.execute(
            "SELECT id FROM tasks WHERE user_id=? AND day=? ORDER BY task_num",
            (msg.from_user.id, today)
        )
        rows = cursor.fetchall()

        for i, row in enumerate(rows, start=1):
            cursor.execute("UPDATE tasks SET task_num=? WHERE id=?", (i, row[0]))

        conn.commit()
        await msg.answer("O‘chirildi 🗑")
    except:
        await msg.answer("Usage: /delete 2")

#-----Report today's progress------
@dp.message_handler(commands=['report'])
async def report(msg: types.Message):
    today = str(date.today())

    cursor.execute(
        "SELECT COUNT(*), SUM(done) FROM tasks WHERE user_id=? AND day=?",
        (msg.from_user.id, today)
    )
    total, done = cursor.fetchone()

    done = done or 0

    if total == 0:
        await msg.answer("Bugungi vazifalar yo'q")
        return

    percent = int(done/total*100)
    await msg.answer(f"Today: {done}/{total} ({percent}%)")


#-------------All time stats--------
@dp.message_handler(commands=['stat'])
async def stat(msg: types.Message):
    cursor.execute(
        "SELECT COUNT(*), SUM(done) FROM tasks WHERE user_id=?",
        (msg.from_user.id,)
    )
    total, done = cursor.fetchone()
    done = done or 0

    await msg.answer(f"Hozirgacha bajarilgan vazifalar: {done}/{total}")


#---------Streak system-----------
@dp.message_handler(commands=['streak'])
async def streak(msg: types.Message):
    today = date.today()
    yesterday = str(today - timedelta(days=1))
    today = str(today)

    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE user_id=? AND day=? AND done=1",
        (msg.from_user.id, yesterday)
    )
    completed = cursor.fetchone()[0]

    cursor.execute(
        "SELECT last_day, streak FROM streaks WHERE user_id=?",
        (msg.from_user.id,)
    )
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO streaks VALUES(?,?,?)",
                       (msg.from_user.id, today, 1))
        conn.commit()
        await msg.answer("🔥 Streak: 1")
        return

    last_day, streak_count = row

    if last_day == yesterday and completed > 0:
        streak_count += 1
    elif last_day != today:
        streak_count = 1

    cursor.execute("UPDATE streaks SET last_day=?, streak=? WHERE user_id=?",
                   (today, streak_count, msg.from_user.id))
    conn.commit()

    await msg.answer(f"🔥 Streak: {streak_count}")


#-------------Reminders-----------------
@dp.message_handler(commands=['remind'])
async def remind(msg: types.Message):
    try:
        args = msg.get_args().split()
        num = int(args[0])
        time_str = args[1]  # HH:MM

        today = str(date.today())

        cursor.execute(
            "INSERT INTO reminders(user_id, day, task_num, remind_time, sent) VALUES(?,?,?,?,0)",
            (msg.from_user.id, today, num, time_str)
        )
        conn.commit()

        await msg.answer(f"⏰ Eslatma qo‘shildi: {num} soat {time_str}")
    except:
        await msg.answer("Foydalanish: /remind 1 18:30")

#-----------Reminder Loop---------------------
async def reminder_loop():
    while True:
        now = datetime.now().strftime("%H:%M")
        today = str(date.today())

        cursor.execute("""
        SELECT user_id, task_num FROM reminders
        WHERE day=? AND remind_time=? AND sent=0
        """, (today, now))

        rows = cursor.fetchall()

        for user_id, task_num in rows:
            cursor.execute("""
            SELECT task FROM tasks
            WHERE user_id=? AND day=? AND task_num=?
            """, (user_id, today, task_num))
            task = cursor.fetchone()

            if task:
                await bot.send_message(user_id, f"⏰ Eslatma: {task[0]}")

            cursor.execute("""
            UPDATE reminders SET sent=1
            WHERE user_id=? AND day=? AND task_num=? AND remind_time=?
            """, (user_id, today, task_num, now))

        conn.commit()
        await asyncio.sleep(30)



async def on_startup(dp):
    asyncio.create_task(reminder_loop())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
