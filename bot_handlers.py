import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import types
import database
import config
import logging

ADMIN_STATES = {}
STATE_IDLE = "IDLE"
STATE_BROADCAST = "BROADCAST"
STATE_SEARCH = "SEARCH"
STATE_DELETE = "DELETE"
STATE_MESSAGE = "BROADCAST_MESSAGE"


# --- ⌨️ ၁။ KEYBOARD for admin FUNCTIONSခွဲထုတ်ခြင်း) ---

def get_admin_main_menu():
    """Admin ရဲ့ ပင်မ Menu ခလုတ်တန်းကို ထုတ်ပေးသော ရိုးရိုး Function"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📊 userlist csv", callback_data="user_csv"),
        types.InlineKeyboardButton("📻 broadcast", callback_data="broadcast"),
        types.InlineKeyboardButton("🔍 search", callback_data="search"),
        types.InlineKeyboardButton("🪦 delete", callback_data="delete"),
        types.InlineKeyboardButton("🌐 Dashboard", url=config.DASHBOARD_LINK)
    )
    return markup

# --- ⌨️ ၁။ KEYBOARD for normal people FUNCTIONSခွဲထုတ်ခြင်း) ---

def get_user_main_menu():
    """Normal User တွေအတွက် ပင်မ Pay ခလုတ်ကို ထုတ်ပေးသော ရိုးရိုး Function"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🧾 pay", callback_data="pay"))
    return markup

#cancel button ‌ေဆာက်ခြင်း

def get_cancel_button(callback_name):
    """မည်သည့်အဆင့်မှာမဆို Cancel ပြန်လုပ်မည့် ခလုတ်ကို ထုတ်ပေးသော Function"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("cancel ❌", callback_data=callback_name))
    return markup


# --- 🤖 ၂။ MAIN BOT HANDLERS REGISTRATION ---

async def register_handlers(bot: AsyncTeleBot):
    #"""လက်ရှိ Bot Instance ထဲသို့ Handler များ အားလုံးကို ထည့်သွင်းပေးမည့် Function normal,vip,admin စစ်ပြီး function ပြမယ်"""

    @bot.message_handler(commands=["start"])
    async def collect_user(message):
        user_id = message.from_user.id
        username = message.from_user.username or f"User_{user_id}"
        
        try:
            await database.add_or_update_user(user_id, username)
            result = await database.check_user(user_id)
            
            if result == "ADMIN":
                try:
                    await bot.send_chat_action(config.ADMIN_ID, "typing")
                    await bot.send_message(config.ADMIN_ID, "**Welcome Admin! Click the button:**", reply_markup=get_admin_main_menu(), parse_mode="markdown")
                except Exception as e:
                    logging.error(f"Admin start message failed: {e}")
            elif result == "VIP":
                report = await database.vip_expire(user_id)
                await bot.send_chat_action(user_id, "typing")
                await bot.send_message(user_id, report)
            else:
                await bot.send_chat_action(user_id, "typing")
                await bot.send_message(user_id, "Click pay and paid to be a Vip!", reply_markup=get_user_main_menu())
        except Exception as e:
            logging.error(f"Error in start command: {e}")

    # 🔄 USER CANCEL: ငွေသွင်းခြင်းကို ပယ်ဖျက်ပြီး မူလ စာသားနှင့် ခလုတ် ပြန်ပြောင်းခြင်း
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_pay")
    async def cancel_process(call):
        user_id = call.message.chat.id
        try:
            await bot.answer_callback_query(call.id, "Canceled")
            await bot.send_chat_action(user_id, "typing")
            await bot.edit_message_text(
                chat_id=user_id, 
                message_id=call.message.message_id, 
                text="Vip ဝင်ရန် ‌ pay ကို နှိပ်ကာ‌ေငွ‌ေပး‌ေချပါ။", 
                reply_markup=get_user_main_menu()
            )
        except Exception as e:
            logging.error(f"Error canceling pay: {e}")

#‌ေငွသွင်းခြင်း

    @bot.callback_query_handler(func=lambda call: call.data == "pay")
    async def paid_vip(call):
        user_id = call.message.chat.id
        vip_amount = "Vip member ကြေး ၁၀ ကျပ်၊ K-pay or wave-pay ph no. 09-123456789 Thို့ငွေလွှဲပါ၊ လွှဲပြီးပါက screenshot ပို့ပါ။"
        try:
            await bot.answer_callback_query(call.id, "Getting info...")
            await bot.send_chat_action(user_id, "typing")
            await bot.edit_message_text(
                chat_id=user_id, 
                message_id=call.message.message_id, 
                text=vip_amount, 
                reply_markup=get_cancel_button("cancel_pay")
            )
        except Exception as e:
            logging.error(f"Error in paid_vip callback: {e}")

#ss ဖမ်းခြင်း၊ ai ကို‌ေပး transaction_id,amount,status ထုတ်၊ bank_notification ရယ် vip ‌ေကြးရယ်နဲ့ တိုက်စစ်၊မှန်ရင်‌ vip ‌ေပး၊ မှားရင် manual စစ်

    @bot.message_handler(content_types=["photo"])
    async def check_ss(message):
        user_id = message.from_user.id
        file_id = message.photo[-1].file_id
        await bot.send_chat_action(user_id, "typing")
        waiting_msg = await bot.send_message(user_id, "လူကြီးမင်း၏ငွေလွှဲပြေစာကိုစစ်ဆေးနေပါသည်၊\n‌ေခတ္တစောင့်ဆိုင်းပေးပါ။")
        analysis_image = await database.verify_and_activate_vip(file_id)
        if analysis_image == "ALREADY_USED":
            await bot.edit_message_text(chat_id = user_id, text = "လူကြီးမင်း၏ငွေလွှဲ‌ေပြစာသည် အသံုးပြုပြီးသား ဖြစ်‌ပါသဖြင့် **VIP ဝင်၍ မရနိုင်ပါ။**", message_id = waiting_msg.message_id)
            return
        elif analysis_image == None:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                        types.InlineKeyboardButton("APPROVE ✅", callback_data=f"CONFIRM_APPROVED_{user_id}"),
                        types.InlineKeyboardButton("REJECT ❌", callback_data=f"CONFIRM_REJECTED_{user_id}")
                    )
            warning = "‌ေငွလွှဲ‌ေပြစာ **မှားမှန်**စစ်‌ေဆး‌ေပးပါ။"
            try:
                await bot.send_photo(chat_id=config.ADMIN_ID, photo=file_id, caption=warning, reply_markup=markup, parse_mode="markdown")
                await bot.edit_message_text(chat_id = user_id, text = "လူကြီးမင်း၏ငွေလွှဲ‌ေပြစာကို **admin မှ စစ်‌ေဆး‌ေနပါပြီ ‌ေခတ္တ‌ေစာင့်ဆိုင်း‌ေပးပါ။**", message_id = waiting_msg.message_id)
            except Exception as e:
                logging.error(f"Admin ထံ‌ေပးပို့ရာ error ဖြစ်‌ေနပါသည်။ error: {e}")
                warning = f"user ထံမှ ‌ေငွလွှဲပံု ‌ေပးပို့ရာတွင် **error ဖြစ်‌ေနပါသည်။** error: {e}"
                await bot.send_message(chat_id=config.ADMIN_ID, text=warning, parse_mode="markdown")

#manual စစ်ခြင်း ပထမ အကြိမ် အတည်ပြု approved or REJECT

    @bot.callback_query_handler(func=lambda call: call.data.startswith("CONFIRM_"))
    async def admin_check(call):
        try:
            data_parts = call.data.split("_")
            action = data_parts[1]
            u_id = data_parts[2]
            
            # Message ထဲမှ မူရင်း photo id ကို ပြန်လည်ရယူခြင်း (Callback Data ထဲ ထည့်မဆံ့သဖြင့်)
            slip_id = call.message.photo[-1].file_id if call.message.photo else "N/A"
            
            if action == "APPROVED":
                text = "အတည်ပြုခြင်းသေချာပါက **Sure** ကိုနှိပ်ပါ၊\nပယ်ဖျက်လိုပါက **Cancel** ကိုနှိပ်ပါ။"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("Sure ✅", callback_data=f"final_accept_{u_id}"),
                    types.InlineKeyboardButton("Cancel 🔙", callback_data=f"final_cancel_{u_id}")
                )
            else:
                text = "ငွေလွှဲကိုငြင်းပယ်ခြင်းသေချာပါက **Decline** ကိုနှိပ်ပါ၊\nပယ်ဖျက်လိုပါက **Cancel** ကိုနှိပ်ပါ။"
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("Decline ❌", callback_data=f"final_decline_{u_id}"),
                    types.InlineKeyboardButton("Cancel 🔙", callback_data=f"final_cancel_{u_id}")
                )
                
            await bot.answer_callback_query(call.id)
            await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption=text, reply_markup=markup)
        except Exception as e:
            logging.error(f"Error in admin_check callback: {e}")
            warning = f"Admin အတည်ပြုရာတွင် error တက်‌ေနပါသည်၊ error: {e}"
            await bot.answer_callback_query(call.id, "Error handling request.", show_alert=True)
            await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption=warning, reply_markup=markup)

#နှစ်ဆင့်အတည်ပြုခြင်း sure and decline

    @bot.callback_query_handler(func=lambda call: call.data.startswith("final_"))
    async def admin_verify(call):
        try:
            data_parts = call.data.split("_")
            verify = data_parts[1]
            u_id = data_parts[2]
            photo_id = call.message.photo[-1].file_id if call.message.photo else "N/A"
            
            if verify == "accept":
                result = await database.admin_accept(u_id, photo_id)
                if result:
                    try:
                        invite_link_obj = await bot.create_chat_invite_link(chat_id=config.VIP_CHANNEL_ID, member_limit=1)
                        success_text = f"သင့်ငွေလွှဲကို admin မှအတည်ပြု လက်ခံလိုက်ပါသည်။\n**သင့်ငွေလွှဲအောင်မြင်ပါတယ်**\nအောက်က vip link ကိုနှိပ်ပြီး member ဝင်နိုင်ပါပြီီ။\nvip link: {invite_link_obj.invite_link}"
                        await bot.send_message(chat_id=int(u_id), text=success_text, parse_mode="markdown")
                        await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption="**APPROVED** ✅ စစ်ဆေးပြီး **one time link **ထုတ်ပေးလိုက်ပါပြီ။", reply_markup=None)
                    except Exception as e:
                        logging.error(f"Failed to send invite link to user {u_id}: {e}")
                        warning = f"Failed to send invite link to user {u_id}: {e}"
                        await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption = f"Failed to send invite link to user {u_id}. error: {e}", reply_markup=None)
                    
            elif verify == "decline":
                await database.admin_decline(int(u_id), photo_id)
                text = "သင့်ငွေလွှဲကို admin မှ **ပယ်ဖျက်**လိုက်ပါသည်၊\nငွေလွှဲ**မအောင်မြင်**ပါ၊\n__vip ဝင်ရန် ထပ်မံငွေလွှဲပါ__"
                try:
                    await bot.send_message(chat_id=int(u_id), text=text, parse_mode="markdown")
                    await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption="**REJECTED** ❌ ဒီ‌ငြင်းပယ်ပြီးပါပြီ။" , reply_markup=None)
                except Exception as e:
                    logging.error(f"Failed to send decline message to user {u_id}. error: {e}")
                    await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption=f"Failed to send decline message to user {u_id}. error: {e}", reply_markup=None)
                
            elif verify == "cancel":
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("APPROVE ✅", callback_data=f"CONFIRM_APPROVED_{u_id}"),
                    types.InlineKeyboardButton("REJECT ❌", callback_data=f"CONFIRM_REJECTED_{u_id}")
                )
                await bot.answer_callback_query(call.id)
                await bot.edit_message_caption(chat_id=config.ADMIN_ID, message_id=call.message.message_id, caption="⚠️ ပြန်လည်ရွေးချယ်ပါရန်...", reply_markup=markup)
        except Exception as e:
            logging.error(f"Error in admin verify callback: {e}")
            await bot.send_message(config.ADMIN_ID, f"**Error** in admin verify callback: {e}")

    # 🔄 ADMIN CANCEL: Admin လုပ်ဆောင်ချက်များကို ပယ်ဖျက်ပြီး Main Menu ပြန်သွားခြင်း
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_function")
    async def cancel_function(call):
        try:
            ADMIN_STATES[config.ADMIN_ID] = STATE_IDLE
            await bot.answer_callback_query(call.id, "Back to Main Menu")
            await bot.edit_message_text(
                chat_id=config.ADMIN_ID, 
                message_id=call.message.message_id, 
                text="**Welcome Admin! Click the button:**", 
                reply_markup=get_admin_main_menu(), 
                parse_mode="markdown"
            )
        except Exception as e:
            logging.error(f"Error in cancel_function: {e}")
            await bot.send_message(config.ADMIN_ID, f"**Error** when admin touchs the cancel button: {e}")
            

#admin ရဲ့ functions

    @bot.callback_query_handler(func=lambda call: call.data in ["user_csv", "broadcast", "search", "delete"])
    async def admin_function(call):
        try:
            if call.data == "user_csv":
                csv_buffer = await database.user_csv()
                await bot.answer_callback_query(call.id, "Uploading docs...")
                await bot.send_document(config.ADMIN_ID, csv_buffer, visible_file_name="all_users_list.csv", caption="📊 **bot စတင်သည့်အချိန်မှ ယနေ့ထိ** user စုစုပေါင်းစာရင်း။", parse_mode="markdown")
            elif call.data in ["broadcast", "search", "delete"]:
                await bot.answer_callback_query(call.id, "Preparing...")
                
                if call.data == "broadcast":
                    text = "📻 သင်ပို့ချင်တာကိုရေးပြီးပို့ပေးပါ၊\nပယ်ဖျက်လိုပါက **cancel** ကိုနှိပ်ပါ။"
                    ADMIN_STATES[config.ADMIN_ID] = STATE_MESSAGE
                elif call.data == "search":
                    text = "🔍 သင်ရှာချင်သူရဲ့နာမည်ကို မှတ်မိသလိုရေးပြီးပို့ပေးပါ၊\nပယ်ဖျက်လိုပါက **cancel** ကိုနှိပ်ပါ။"
                    ADMIN_STATES[config.ADMIN_ID] = STATE_SEARCH
                elif call.data == "delete":
                    text = "🪦 သင်ဖျက်ချင်သူရဲ့ **ID** ရေးပြီးပို့ပေးပါ၊\nID ရှာရန် cancel နှိပ်ပြီး search ဖြင့်ရှာပါ။"
                    ADMIN_STATES[config.ADMIN_ID] = STATE_DELETE
                    
                await bot.edit_message_text(
                    chat_id=config.ADMIN_ID, 
                    message_id=call.message.message_id, 
                    text=text, 
                    reply_markup=get_cancel_button("cancel_function"), 
                    parse_mode="markdown"
                )
        except Exception as e:
            logging.error(f"Error in admin_function callback: {e}")

# [🔥 ပြင်ဆင်လိုက်သည့်နေရာ - အဆင့်မြင့် အန္တရာယ်ကင်း BROADCAST စနစ်]
    @bot.message_handler(func=lambda message: ADMIN_STATES.get(config.ADMIN_ID) == STATE_MESSAGE)
    async def ask_message(message):
        ADMIN_STATES[config.ADMIN_ID] = STATE_IDLE
        text = message.text
        if not text:
            await bot.reply_to(message, "စာသားမရှိ၍ပို့လို့မရပါ၊ စာသားရေးပြီးထပ်မံပို့ပါ။")
            return
            
        try:
            people = await database.all_user()
            if not people:
                await bot.reply_to(message, "📢 **broadcast** လုပ်ရန် user မရှိသေးပါ ခဗျ။")
                return
                
            progress_msg = await bot.reply_to(message, "📢 Broadcast စတင်ပို့ဆောင်နေပါပြီ...")
            success_count = 0
                
            for one in people:
                try:
                    await bot.send_message(one, f"**Admin notice** 🔔\n\n{text}", parse_mode="markdown")
                    success_count += 1
                    await asyncio.sleep(0.05)  # Telegram Rate Limit မမိစေရန် ခေတ္တနားခြင်း
                except Exception:
                    pass  # User က Block ထားလျှင် ကျော်ခွသွားမည်
                    
            await bot.edit_message_text(
                chat_id=config.ADMIN_ID,
                message_id=progress_msg.message_id,
                text=f"📢 broadcast လုပ်ခြင်းအောင်မြင်ပါတယ်၊\n✅ အောင်မြင်: {success_count} ဦး / 📊 စုစုပေါင်း: {len(people)} ဦး"
            )
        except Exception as e:
            logging.error(f"Error in broadcast function: {e}")
            await bot.reply_to(message, "❌ Broadcast လုပ်ဆောင်ရာတွင် စနစ်ချို့ယွင်းမှု ဖြစ်ပွားခဲ့သည်။")

#user ရှာခြင်း

    @bot.message_handler(func=lambda message: ADMIN_STATES.get(config.ADMIN_ID) == STATE_SEARCH)
    async def search_message(message):
        ADMIN_STATES[config.ADMIN_ID] = STATE_IDLE
        text = message.text
        if not text:
            await bot.reply_to(message, "စာသားမရှိ၍ user ကို **ရှာမရပါ။**")
            return
            
        try:
            user_data = await database.search_user(text)
            if not user_data:
                await bot.reply_to(message, "ပေးပို့သောနာမည်နှင့် တူညီသော **user မရှိပါခဗျ။**")
                return
                
            report = f"**{text} နှင့်ဆင်တူသော user ရှာခြင်းရလဒ်**\n\n"
            for one in user_data:
                user_id, username, role, expire_date, last_activity, started_time = one
                report += f"🆔 id: `{user_id}`\n👤 name: @{username}\n💎 status: {role}\n📅 expire: {expire_date}\n\n"
            await bot.reply_to(message, report, parse_mode="markdown")
        except Exception as e:
            logging.error(f"Error in search function: {e}")

#user ဖျက်ခြင်း

    @bot.message_handler(func=lambda message: ADMIN_STATES.get(config.ADMIN_ID) == STATE_DELETE)
    async def delete_message(message):
        ADMIN_STATES[config.ADMIN_ID] = STATE_IDLE
        try:
            u_id = int(message.text)
            delete_user = await database.delete_user(u_id)
            if delete_user:
                # 💡 parse_mode ကို HTML ပြောင်းပြီး tag များကို HTML အဖြစ် ပြောင်းလဲလိုက်ပါသည်
                await bot.ban_chat_member(chat_id=config.VIP_CHANNEL_ID, user_id=user_id)
                await bot.unban_chat_member(chat_id=config.VIP_CHANNEL_ID, user_id=user_id)
                success_msg = f"<b>Deleted</b> 🦹\nUsername: {delete_user} \nuser_id: <code>{u_id}</code>\nကိုအောင်မြင်စွာ ဖျက်ပြီးပါပြီ။"
                await bot.reply_to(message, success_msg, parse_mode="HTML")
            else:
                await bot.reply_to(message, "❌ ယင်း ID ဖြင့် သုံးစွဲသူအား Database ထဲတွင် ရှာမတွေ့ပါ။")
        except ValueError:
            await bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ဂဏန်း (User ID) စစ်စစ်ကိုသာ ရိုက်နှိပ်ပေးပါဗျာ။")
        except Exception as e:
            logging.exception(f"Error in delete function: {e}")
