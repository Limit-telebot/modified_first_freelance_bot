import os
import logging

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    handlers=[
        logging.FileHandler("bot_log.txt", encoding="utf-8"), # .txt ဟု ပြင်ဆင်ပြီး
        logging.StreamHandler()
    ]
)

import uvicorn
from server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logging.info(f"Starting Ai Payment Bot Server on port {port}...")
    
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
