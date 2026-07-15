import os
import aiosqlite
import datetime
import csv
import io
import config
import asyncio # 💡 Queue သုံးရန်အတွက် ထည့်သွင်းခြင်း


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "aipay_store.db")


# =====================================================================
# 🛠️ ASYNCIO QUEUE SYSTEM ENGINE (ဗဟိုထိန်းချုပ်ရေးအင်ဂျင်)
# =====================================================================

# 1. အလုပ်များကို အစီအစဉ်တကျ တန်းစီမှတ်မည့် စာရင်းစာအုပ် ဆောက်ခြင်း
db_queue = asyncio.Queue()

async def db_worker():
    """
    နောက်ကွယ် (Background) တွင် ၂၄ နာရီပတ်လုံး အမြဲပွင့်နေပြီး Queue ထဲမှ အလုပ်များကို
    တစ်ကြိမ်လျှင် တစ်ခုတည်း (Sequential) စနစ်တကျ ထုတ်ယူကာ Database ထဲသို့ ရေးမည့် အလုပ်သမား။
    """
    while True:
        # Queue ထဲတွင် အလုပ်ရှိမရှိ စောင့်ဖတ်မယ် (အလုပ်မရှိရင် ဒီနေရာမှာ ငြိမ်စောင့်နေပါမယ်)
        task = await db_queue.get()
        func, args, kwargs, future = task
        
        try:
            # 💡 ဤနေရာတွင် မင်းရေးထားသော ပင်မလုပ်ဆောင်ချက်များကို တစ်ခုချင်းစီ အလှည့်ကျ ခေါ်ယူမောင်းနှင်ခြင်းဖြစ်သည်
            result = await func(*args, **kwargs)
            future.set_result(result) # ရလာသော အဖြေကို အလွတ်စာအိတ် (Future) ထဲ ထည့်ပေးလိုက်ခြင်း
        except Exception as e:
            future.set_exception(e) # အကယ်၍ Error တက်ပါကလည်း Error အဖြေကို ထည့်ပေးခြင်း
        finally:
            db_queue.task_done() # အလုပ်တစ်ခု ပြီးမြောက်ကြောင်း စနစ်ကို အသိပေးခြင်း

async def execute_in_queue(func, *args, **kwargs):
    """
    တခြား bot_handlers သို့မဟုတ် server ဘက်မှ လာခေါ်သမျှ Database ရေး/ဖတ် အလုပ်အားလုံးကို
    တိုက်ရိုက်မလုပ်စေဘဲ Queue ထဲသို့ သွားရောက် တန်းစီခိုင်းစေမည့် ကြားခံမန်နေဂျာ Function။
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future() # 💡 အဖြေပြန်သယ်ရန် "Future အလွတ်စာအိတ်" ဆောက်ခြင်း
    
    # အလုပ်လုပ်မည့် Function၊ ပါရာမီတာများနှင့် စာအိတ်ကို Queue ထဲ ထည့်လိုက်ခြင်း
    await db_queue.put((func, args, kwargs, future))
    
    # မိမိအလှည့်ကျလို့ အလုပ်ပြီးဆုံးပြီး စာအိတ်ပွင့်လာမည့်အချိန်အထိ စောင့်ကာ အဖြေကို ပြန်ပေးခြင်း
    return await future

# =====================================================================
# 🗄️ DATABASE OPERATIONS (ပင်မ လုပ်ဆောင်ချက်များ)
# =====================================================================

async def init_db():
    """
    db tables များ‌ေဆာက်ခြင်း၊ အားလံုး၏အစ
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        # 💡 SQLite အချင်းချင်း လော့ခ်မကျစေရန် ၃၀ စက္ကန့် စောင့်ဆိုင်းမှုကိုပါ အပိုဆောင်း ထည့်သွင်းပေးထားပါသည်
        await conn.execute("PRAGMA busy_timeout = 30000;")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user(
                user_id INTEGER PRIMARY KEY, 
                username TEXT, 
                role TEXT DEFAULT 'user', 
                expire_date TEXT, 
                last_activity TEXT,
                started_time TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS record(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                time TEXT, 
                file_id TEXT UNIQUE,
                status TEXT
            ) 
        """)
        await conn.commit()
    
    # 💡 စနစ်စတင်ပွင့်ကတည်းက နောက်ကွယ်တွင် Worker ကြီး တစ်ပြိုင်နက် အလုပ်လုပ်နေစေရန် နှိုးလိုက်ခြင်းဖြစ်သည်
    asyncio.create_task(db_worker())

# ---------------------------------------------------------------------
# ---------------------------------------------------------------------

async def _add_or_update_user_direct(user_id, username):
    """
    /start လုပ်‌ေသာ user တိုင်းကို မှတ်သားခြင်းနဲ့ အဆင့်ခွဲခြင်း
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    role = "ADMIN" if user_id == config.ADMIN_ID else "user"
    async with aiosqlite.connect(DB_NAME) as conn:
        await conn.execute("""
            INSERT INTO user (user_id, username, role, last_activity, started_time) 
            VALUES(?, ?, ?, ?, ?) 
            ON CONFLICT (user_id) DO UPDATE SET username = ?, last_activity = ?
        """, (user_id, username, role, now, now, username, now))
        await conn.commit()

async def _verify_and_activate_vip_direct(file_id):
    """ slip ကိုအသံုးပြုပြီးသားဟုတ်မဟုတ်စစ်တဲ့ func မဟုတ်ရင် admin ဆီပို့မယ့် func
 """
    async with aiosqlite.connect(DB_NAME) as conn:
        async with conn.execute("SELECT id FROM record WHERE file_id = ?", (file_id,)) as cursor:
            if await cursor.fetchone():
                return "ALREADY_USED"
            else:
              return None
                
async def _admin_accept_direct(u_id, photo_id):
    """
    admin မှ manual စစ်ပြီး approve ‌ေသာ  Function၊
    """
    expire_date = datetime.datetime.now() + datetime.timedelta(minutes=1)
    expire_str = expire_date.strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as conn:
        await conn.execute("UPDATE user SET role = 'VIP', expire_date = ?, last_activity = ? WHERE user_id = ?", (expire_str, expire_str, u_id))
        await conn.execute("""INSERT INTO record (user_id, time, file_id, status) VALUES (?, ?, ?, 'APPROVED')""", (u_id, expire_str, photo_id))
        await conn.commit()
    return True
    
async def _admin_decline_direct(u_id, photo_id):
    """
    admin မှ manual စစ်ပြီး  decline ‌ေသာ  Function၊
    """
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as conn:
        await conn.execute("""INSERT INTO record (user_id, time, file_id, status) VALUES (?, ?, ?, 'DECLINE')""", (u_id, time, photo_id))
        await conn.commit()
    return False

async def _delete_user_direct(user_id):
    """
    admin မှ user ကို bot မှာတဆင့် delete ‌ေသာ function 
    """
    name = None
    async with aiosqlite.connect(DB_NAME) as conn:
        # 💡 ဒေတာဘေ့စ် လော့ခ်မကျစေရန် SELECT စာကြောင်း ပြီးဆုံးမှ DELETE အလုပ်ကို သီးသန့် ဆက်လုပ်စေထားပါသည်
        async with conn.execute("SELECT username FROM user WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                name = row[0]
        if name:
            await conn.execute("DELETE FROM user WHERE user_id = ?", (user_id,))
            await conn.execute("DELETE FROM record WHERE user_id = ?", (user_id,))
            await conn.commit()
    return name

async def _get_and_clean_expired_vips_direct():
    """
    သက်တမ်းကုန်‌ေသာ vip များကို normal အဖြစ်‌ေပြာင်းခြင်း
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    expired_users = []
    async with aiosqlite.connect(DB_NAME) as conn:
        async with conn.execute("SELECT username, user_id FROM user WHERE role = 'VIP' AND expire_date < ?", (now,)) as cursor:
            user_data = await cursor.fetchall()
              
        if not user_data:
            return expired_users 
              
        for row in user_data:
            username, user_id = row
            await conn.execute("UPDATE user SET role = 'user', expire_date = 'Expired' WHERE user_id = ?", (user_id,))
            expired_users.append({"user_id": user_id, "username": username})
              
        await conn.commit()
    return expired_users

# =====================================================================
# 🎯 PUBLIC API FUNCTIONS (မင်းရဲ့ မူလ ပြင်ပခေါ်ယူမည့် အဓိက Def နာမည်များ)
# =====================================================================
# 💡 တခြား ဖိုင်များမှ လှမ်းခေါ်လျှင် ၎င်းတို့သည် အလိုအလျောက် Queue ထဲဝင်ပြီး စနစ်တကျ အလှည့်ကျ လုပ်ဆောင်သွားမည်။

async def add_or_update_user(user_id, username):
    return await execute_in_queue(_add_or_update_user_direct, user_id, username)

async def verify_and_activate_vip(file_id):
    return await execute_in_queue(_verify_and_activate_vip_direct, file_id)

async def admin_accept(u_id, photo_id):
    return await execute_in_queue(_admin_accept_direct, u_id, photo_id)

async def admin_decline(u_id, photo_id):
    return await execute_in_queue(_admin_decline_direct, u_id, photo_id)

async def delete_user(user_id):
    return await execute_in_queue(_delete_user_direct, user_id)

async def get_and_clean_expired_vips():
    return await execute_in_queue(_get_and_clean_expired_vips_direct)

# ---------------------------------------------------------------------
# 💡 စာဖတ်ခြင်း (SELECT/READ သီးသန့်) Functions များဖြစ်ကြပြီး SQLite သည် 
# ပြိုင်တူဖတ်ခြင်းကို ကောင်းစွာလက်ခံနိုင်သဖြင့် ၎င်းတို့ကို Queue ထဲထည့်ရန်မလိုဘဲ တိုက်ရိုက်အလုပ်လုပ်စေပါသည်။
# ---------------------------------------------------------------------

async def check_user(user_id):
    """
    /start လာနှိပ်တဲ့‌ေကာင်‌ေတွကို vip,admin,user ခဲွခြား‌ေပးမယ့် Functions
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        async with conn.execute("SELECT role, expire_date FROM user WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                role, expire_str = row
                if role == "ADMIN":
                    return "ADMIN"
                if expire_str and expire_str not in ['Expired', 'null']:
                    try:
                        expire_date = datetime.datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
                        if datetime.datetime.now() < expire_date:
                            return "VIP"
                    except ValueError:
                        pass
    return False

async def vip_expire(user_id):
    """
    /start လာနှိပ်တဲ့ ‌ေကာင်ကို vip ဆိုရင် ကျန်တဲ့သက်တမ်းကို တိတိကျကျ ပြမယ့် Functions
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        async with conn.execute("SELECT expire_date FROM user WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result and result[0] and result[0] not in ['Expired', 'null']:
                vip_left = result[0]
                try:
                    cal_time = datetime.datetime.strptime(vip_left, "%Y-%m-%d %H:%M:%S")
                    if cal_time > datetime.datetime.now():
                        left_cal = cal_time - datetime.datetime.now()
                        hours, remainder = divmod(left_cal.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        return f"You are VIP! Time left: {left_cal.days} days, {hours} hours, {minutes} minutes."
                    else:
                        return "Vip life run out! send /start and recharge to be a Vip!"
                except ValueError:
                    return "Vip life run out! send /start and recharge to be a Vip!"
            else:
                return "You have no vip time! send /start and recharge to be a Vip!"

async def get_dashboard_data():
    """
    admin အတွက် dashboard data ထုတ်‌ေပးမယ့် function
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        conn.row_factory = aiosqlite.Row
        query = """
            SELECT u.user_id, u.username, u.role, u.expire_date, u.last_activity, u.started_time, 
                   r.id, r.time, r.status 
            FROM user u LEFT JOIN record r ON u.user_id = r.user_id ORDER BY u.last_activity DESC
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def search_user(text):
    """
    user ရှာ‌ေပးမယ့် function
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        async with conn.execute("SELECT user_id, username, role, expire_date, last_activity, started_time FROM user WHERE username LIKE ?", (f"%{text}%",)) as cursor:
            user_data = await cursor.fetchall()
    return user_data

async def user_csv():
    """
    user data ကို csv အဖြစ်ထုတ်‌ေပးမယ့် function
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        conn.row_factory = aiosqlite.Row
        query = """SELECT u.user_id, u.username, u.role, u.expire_date, u.last_activity, u.started_time, r.id, r.time, r.file_id, r.status FROM user u LEFT JOIN record r ON u.user_id = r.user_id"""
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Role", "Expire Date", "Last Activity", "Started Time", "ID", "Time", "File ID", "Status"])
    for row in rows:
        writer.writerow([row["user_id"], row["username"], row["role"], row["expire_date"] or 0, row["last_activity"], row["started_time"], row["id"] or "no slip", row["time"] or "N/A", row["file_id"] or "no slip", row["status"] or "N/A"])
    output.seek(0)
    return output

async def all_user():
    """
    Admin ကိုဖယ်ပြီး VIP နှင့် ပုံမှန် user တွေကိုပဲ Broadcast လုပ်ဖို့ ထုတ်ပေးမည့် function
    """
    async with aiosqlite.connect(DB_NAME) as conn:
        async with conn.execute("SELECT user_id FROM user WHERE role IN ('user', 'VIP')") as cursor:
            rows = await cursor.fetchall()
            user_ids = [row[0] for row in rows] 
            
    return user_ids
