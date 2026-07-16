from fastapi import FastAPI, Header, Request, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from telebot.async_telebot import AsyncTeleBot
from telebot import types
import bot_handlers
import logging
import database
import config
import asyncio
import scheduler
import re

templates = Jinja2Templates(directory="templates")
bot = AsyncTeleBot(config.BOT_TOKEN)
app = FastAPI(title="Ai-Powered Payment Bot Gateway")
security = HTTPBasic()

async def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "Limit")
    correct_password = secrets.compare_digest(credentials.password, "123456")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "basic"} 
        )
    return correct_username


@app.on_event("startup")
async def start_event():
    await database.init_db()
    logging.info("Database initialized...")
    

    await bot_handlers.register_handlers(bot)
    logging.info("Bot Handlers registered successfully!")
    
    scheduler.start_scheduler(bot) 
    logging.info("Background Auto-Kick System fully activated!")
  
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    try:
        data = await database.get_dashboard_data()
        return templates.TemplateResponse(request=request, name="dashboard.html", context={"users": data})
    except Exception as e:
        logging.error(f"Dashboard error: {e}")
        return templates.TemplateResponse(request=request, name="dashboard.html", context={"users": []})
  
@app.post(f"/{config.BOT_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        json_str = await request.json()
        update = types.Update.de_json(json_str)
        asyncio.create_task(bot.process_new_updates([update])) 
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    return {"status": "Bot is running!"}

