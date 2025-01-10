import logging
import sqlite3
import time
import openai
from threading import Lock
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from config import OPENAI_API_KEY
from database import get_connection
from payments import create_invoice
from utils import (
    fetch_user_history, fetch_user_favorites,
    fetch_shared_topics, generate_qr_code,
    fetch_payment_history, fetch_user_stats
)

# Initialize OpenAI API key and logger
openai.api_key = OPENAI_API_KEY
logger = logging.getLogger(__name__)

# Initialize a global lock for database operations
db_lock = Lock()

# Database helper functions
def get_user_balance(telegram_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_user_balance(telegram_id: int, amount: int):
    """Update the user's balance with a retry mechanism and global lock to handle database locks."""
    for attempt in range(5):
        try:
            with db_lock:
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO users (telegram_id, balance) VALUES (?, 0)", (telegram_id,))
                c.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, telegram_id))
                conn.commit()
                conn.close()
            return
        except sqlite3.OperationalError as e:
            logger.warning(f"Database locked on update_user_balance attempt {attempt}: {e}")
            time.sleep(0.2)
    logger.error("Failed to update user balance after several attempts.")

def log_history(telegram_id: int, query: str, response: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO history (telegram_id, query, response) VALUES (?, ?, ?)", (telegram_id, query, response))
    conn.commit()
    conn.close()

def save_favorite(telegram_id: int, content: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO favorites (telegram_id, content) VALUES (?, ?)", (telegram_id, content))
    conn.commit()
    conn.close()

def share_topic(telegram_id: int, content: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO shared_topics (telegram_id, content) VALUES (?, ?)", (telegram_id, content))
    conn.commit()
    conn.close()

def process_chatgpt_query(user_query: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_query}],
            stream=False,
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "Sorry, something went wrong while trying to get an answer. Please try again later."

def start(update: Update, context: CallbackContext):
    """Handle the /start command and display a static main menu."""
    user_first_name = update.message.from_user.first_name
    welcome_text = (
        f"Hello {user_first_name}! 👋\n\n"
        "I'm your friendly ChatGPT bot. You can ask me questions, save your favorite answers, "
        "and share interesting topics with friends.\n\n"
        "Use the menu below to navigate through options."
    )
    menu_buttons = [
        ['❓ Questions Left', '💰 Buy Queries'],
        ['📜 History', '⭐️ Favorites'],
        ['📢 Shared Topics'],
        ['💳 Payment History', '📊 My Stats']
    ]
    reply_markup = ReplyKeyboardMarkup(menu_buttons, resize_keyboard=True)
    update.message.reply_text(welcome_text, reply_markup=reply_markup)

def handle_message(update: Update, context: CallbackContext):
    """Handle incoming text messages and navigate based on static menu selections."""
    telegram_id = update.message.from_user.id
    text = update.message.text.strip().lower()

    if text == "❓ questions left":
        balance = get_user_balance(telegram_id)
        response = f"You have {balance} queries remaining."
        if balance < 5:
            response += "\n\nYou're running low on queries. Consider buying more to keep enjoying our service."
        update.message.reply_text(response)
    elif text == "💰 buy queries":
        keyboard = [
            [InlineKeyboardButton("🔹 Buy 1 Query (50 sat)", callback_data='buy_1')],
            [InlineKeyboardButton("🔹 Buy 10 Queries (450 sat)", callback_data='buy_10')],
            [InlineKeyboardButton("🔹 Buy 100 Queries (3200 sat)", callback_data='buy_100')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Select an option to purchase queries:", reply_markup=reply_markup)
    elif text == "📜 history":
        history_text = fetch_user_history(telegram_id)
        update.message.reply_text(f"📜 Your Recent History:\n\n{history_text}")
    elif text == "⭐️ favorites":
        favorites_text = fetch_user_favorites(telegram_id)
        update.message.reply_text(f"⭐️ Your Favorites:\n\n{favorites_text}")
    elif text == "📢 shared topics":
        shared_topics_text = fetch_shared_topics(telegram_id)
        update.message.reply_text(f"📢 Shared Topics:\n\n{shared_topics_text}")
    elif text == "💳 payment history":
        history = fetch_payment_history(telegram_id)
        update.message.reply_text(f"💳 Your Payment History:\n\n{history}")
    elif text == "📊 my stats":
        stats = fetch_user_stats(telegram_id)
        update.message.reply_text(f"📊 Your Stats:\n\n{stats}")
    else:
        # Treat as a ChatGPT query if text doesn't match any static options
        balance = get_user_balance(telegram_id)
        if balance <= 0:
            update.message.reply_text(
                "Oops! It looks like you don't have any queries left. 😞\n\n"
                "After payment, it may take up to 2 minutes for your new queries to be available."
            )
            invoice_data = create_invoice(amount=50, memo="Single query credit purchase")
            payment_request = invoice_data.get("payment_request", "Error generating invoice")
            qr_image = generate_qr_code(payment_request)
            update.message.reply_text(f"👉 Please pay the following invoice:\n`{payment_request}`", parse_mode='Markdown')
            update.message.reply_photo(photo=qr_image, caption="📱 Scan this QR code to pay.")
            return

        response_text = process_chatgpt_query(text)
        update.message.reply_text(response_text)
        update_user_balance(telegram_id, -1)
        log_history(telegram_id, text, response_text)

def handle_purchase_callback(update: Update, context: CallbackContext):
    """Handle inline button callbacks for purchasing queries."""
    query = update.callback_query
    query.answer()  # Acknowledge the callback to remove loading state
    telegram_id = query.from_user.id
    data = query.data

    if data.startswith('buy_'):
        if data == 'buy_1':
            queries = 1
            satoshi = 50
        elif data == 'buy_10':
            queries = 10
            satoshi = 450
        elif data == 'buy_100':
            queries = 100
            satoshi = 3200
        else:
            query.edit_message_text("Invalid purchase option selected.")
            return

        # Create invoice using LNBits
        invoice_data = create_invoice(amount=satoshi, memo=f"Bulk purchase of {queries} queries")
        logger.info(f"Invoice Data: {invoice_data}")  # Log invoice data for debugging
        payment_request = invoice_data.get("payment_request", "Error generating invoice")
        payment_hash = invoice_data.get("payment_hash", "")

        # Insert transaction into database with retry mechanism and global lock
        for attempt in range(5):
            try:
                with db_lock:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO transactions (telegram_id, invoice_id, payment_hash, amount, queries, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (telegram_id, payment_hash, payment_hash, satoshi, queries, "pending"))
                    conn.commit()
                    conn.close()
                break
            except sqlite3.OperationalError as e:
                logger.warning(f"Database locked on handle_purchase_callback attempt {attempt}: {e}")
                time.sleep(0.2)
        else:
            logger.error("Failed to insert transaction after several attempts.")
            query.edit_message_text("Sorry, an error occurred while processing your purchase. Please try again later.")
            return

        # Generate QR code for payment
        qr_image = generate_qr_code(payment_request)

        # Update message with invoice text and send QR code
        new_text = f"🛒 Invoice for {queries} queries:\n\n`{payment_request}`"
        query.edit_message_text(new_text, parse_mode='Markdown')
        query.message.reply_photo(photo=qr_image, caption="📱 Scan this QR code to pay.")

def payment_history(update: Update, context: CallbackContext):
    """Show the user their recent payment history."""
    telegram_id = update.message.from_user.id
    history = fetch_payment_history(telegram_id)
    update.message.reply_text(f"💳 Your Payment History:\n\n{history}")

def user_stats(update: Update, context: CallbackContext):
    """Show the user their personal statistics."""
    telegram_id = update.message.from_user.id
    stats = fetch_user_stats(telegram_id)
    update.message.reply_text(f"📊 Your Stats:\n\n{stats}")
