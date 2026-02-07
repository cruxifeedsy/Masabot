import json
import pandas as pd
import yfinance as yf
import asyncio
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# Load access codes
with open("users.json") as f:
    allowed_users = json.load(f)["users"]

# Currency pairs and expiry options
PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "EURGBP=X", "EURJPY=X"]
EXPIRIES = ["5s", "15s", "1m", "2m", "3m", "5m", "10m"]

# Store user sessions
user_sessions = {}

# --- Technical analysis ---
def analyze(pair):
    try:
        df = yf.download(pair, period="1d", interval="1m")
        if df.empty:
            return "WAIT", 50
        
        rsi = RSIIndicator(df['Close']).rsi().iloc[-1]
        macd = MACD(df['Close']).macd_diff().iloc[-1]
        ma = SMAIndicator(df['Close'], window=14).sma_indicator().iloc[-1]
        
        signal = "WAIT"
        prob = 50

        # Simple strategy logic
        if rsi < 30 and macd > 0:
            signal = "BUY"
            prob = 85
        elif rsi > 70 and macd < 0:
            signal = "SELL"
            prob = 85
        
        return signal, prob
    except:
        return "WAIT", 50

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter your access code:")

async def access_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    chat_id = update.message.chat_id
    if code in allowed_users:
        user_sessions[chat_id] = {"authenticated": True}
        buttons = [[InlineKeyboardButton(p.replace("=X",""), callback_data=f"pair_{p}")] for p in PAIRS]
        await update.message.reply_text("✅ Access granted. Select a currency pair:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("❌ Invalid code. Try again.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    # Select pair
    if data.startswith("pair_"):
        pair = data.split("_")[1]
        user_sessions[chat_id]["pair"] = pair
        buttons = [[InlineKeyboardButton(e, callback_data=f"exp_{e}")] for e in EXPIRIES]
        await query.edit_message_text(f"Selected {pair.replace('=X','')}. Choose expiry time:", reply_markup=InlineKeyboardMarkup(buttons))

    # Select expiry
    elif data.startswith("exp_"):
        expiry = data.split("_")[1]
        user_sessions[chat_id]["expiry"] = expiry
        pair = user_sessions[chat_id]["pair"]
        await query.edit_message_text(f"⏳ Generating signal for {pair.replace('=X','')} with expiry {expiry}...")
        
        # Countdown notification 1 min before signal if expiry > 1m
        if "m" in expiry:
            await context.bot.send_message(chat_id=chat_id, text="⏰ Signal will be sent in 1 minute...")
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(3)  # short wait for seconds signals

        signal, prob = analyze(pair)
        img_path = "buy.png" if signal == "BUY" else "sell.png"
        description = f"Currency Pair: {pair.replace('=X','')}\nExpiry: {expiry}\nVolatility: Moderate\nProbability: {prob}%"

        buttons = [
            [InlineKeyboardButton("🍀Repeat", callback_data="repeat")],
            [InlineKeyboardButton("↩️Back", callback_data="back")]
        ]
        await context.bot.send_photo(chat_id=chat_id, photo=open(img_path,"rb"), caption=description, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "repeat":
        pair = user_sessions[chat_id]["pair"]
        expiry = user_sessions[chat_id]["expiry"]
        await context.bot.send_message(chat_id=chat_id, text="⏳ Generating another signal...")
        signal, prob = analyze(pair)
        img_path = "buy.png" if signal == "BUY" else "sell.png"
        description = f"Currency Pair: {pair.replace('=X','')}\nExpiry: {expiry}\nVolatility: Moderate\nProbability: {prob}%"
        await context.bot.send_photo(chat_id=chat_id, photo=open(img_path,"rb"), caption=description)

    elif data == "back":
        buttons = [[InlineKeyboardButton(p.replace("=X",""), callback_data=f"pair_{p}")] for p in PAIRS]
        await query.edit_message_text("Select a currency pair:", reply_markup=InlineKeyboardMarkup(buttons))

async def manual_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in user_sessions and "pair" in user_sessions[chat_id]:
        pair = user_sessions[chat_id]["pair"]
        expiry = user_sessions[chat_id].get("expiry", "5s")
        await update.message.reply_text("⏳ Generating manual signal...")
        signal, prob = analyze(pair)
        img_path = "buy.png" if signal == "BUY" else "sell.png"
        description = f"Currency Pair: {pair.replace('=X','')}\nExpiry: {expiry}\nVolatility: Moderate\nProbability: {prob}%"
        await context.bot.send_photo(chat_id=chat_id, photo=open(img_path,"rb"), caption=description)
    else:
        await update.message.reply_text("Select a currency pair first using /start.")

# --- App Setup ---
app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("manual", manual_signal))  # manual signal anytime
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, access_code))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()