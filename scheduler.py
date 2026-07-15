from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telebot.async_telebot import AsyncTeleBot
from telebot import types
import database
import config
import logging

# bot_handlers ထဲက Keyboard ခလုတ်ကို လှမ်းယူရန်
from bot_handlers import get_user_main_menu 

async def check_and_kick_expired_user(bot: AsyncTeleBot):
  try:
        # database ဘက်ကနေ သက်တမ်းကုန်သူတွေကို သန့်စင်ပြီး စာရင်းတောင်းမယ်
    expired_list = await database.get_and_clean_expired_vips()
        
    for user in expired_list:
      user_id = user["user_id"]
      username = user["username"]
            
      try:
                # Telegram Channel ထဲမှ Kick ထုတ်ခြင်း (Ban ပြီး ပြန် Unban ရန်)
        await bot.ban_chat_member(chat_id=config.VIP_CHANNEL_ID, user_id=user_id)
        await bot.unban_chat_member(chat_id=config.VIP_CHANNEL_ID, user_id=user_id)
                
                # User ထံ သတိပေးစာပို့ခြင်း
        await bot.send_message(
                    chat_id=user_id, 
                    text="လူကြီးမင်းရဲ့ VIP သက်တမ်း ကုန်ဆုံးသွား၍ channel မှ ထွက်လိုက်ရပါတယ်ဗျ။\n**VIP** ပြန်ဝင်ရန် *pay* ခလုတ်ကို နှိပ်ပါဗျ။", 
                    reply_markup=get_user_main_menu(), 
                    parse_mode="Markdown"
                )
                
                # Admin ထံ Log ပို့ခြင်း
        await bot.send_message(
                    chat_id=config.ADMIN_ID, 
                    text=f"🪓 **VIP သက်တမ်းကုန်၍ Channel မှ ထုတ်ပစ်လိုက်သော User:**\n• **User ID:** `{user_id}`\n• **Name:** @{username}", 
                    parse_mode="Markdown"
                )
      except Exception as tg_err:
                logging.error(f"Error processing kick/message for user {user_id}: {tg_err}")
                
  except Exception as e:
        logging.error(f"Expired VIP Scheduler Error: {e}")

def start_scheduler(bot: AsyncTeleBot):
  """Scheduler ကို စတင်ပြီး ၃၀ စက္ကန့်တစ်ကြိမ် အလုပ်လုပ်ခိုင်းမည့် Function"""
  scheduler = AsyncIOScheduler()
    # bot instance ကိုပါ job ထဲ ထည့်ပေးလိုက်ခြင်း
  scheduler.add_job(check_and_kick_expired_user, "interval", seconds=30, args=[bot])
  scheduler.start()
  logging.info("APScheduler အား Background တွင် အောင်မြင်စွာ စတင်လိုက်ပါပြီ...")


