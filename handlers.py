import logging
import sqlite3
import openai
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from config import OPENAI_API_KEY
from database import get_connection
from payments import create_invoice, check_payment
from utils import (
    fetch_user_history, fetch_user_favorites,
    fetch_shared_topics, generate_qr_code,
    fetch_payment_history, fetch_user_stats
)

# Initialize OpenAI API key
openai.api_key = OPENAI_API_KEY
logger = logging.getLogger(__name__)

# Database helper functions
def get_user_balance(telegram_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_user_balance(telegram_id: int, amount: int):
    conn = get_connection()
    c = conn.cursor()
    # Ensure user exists
    c.execute("INSERT OR IGNORE INTO users (telegram_id, balance) VALUES (?, 0)", (telegram_id,))
    # Update user balance
    c.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, telegram_id))
    conn.commit()
    conn.close()

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

# OpenAI Query Function
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

# Command Handlers
def start(update: Update, context: CallbackContext):
    """Handle the /start command and display main menu."""
    user_first_name = update.message.from_user.first_name
    welcome_text = (f"Hello {user_first_name}! 👋\n\n"
                    "I'm your friendly ChatGPT bot. You can ask me questions, save your favorite answers, "
                    "and even share interesting topics with friends. Use the menu below to get started.")
    update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard(update.message.from_user.id)
    )

def main_menu_keyboard(telegram_id: int):
    """Generate dynamic inline keyboard based on user status."""
    balance = get_user_balance(telegram_id)
    balance_button = InlineKeyboardButton(f"Balance: {balance} queries", callback_data='balance')
    keyboard = [
        [balance_button],
        [InlineKeyboardButton("History 📜", callback_data='history')],
        [InlineKeyboardButton("Favorites ⭐️", callback_data='favorites')],
        [InlineKeyboardButton("Shared Topics 📢", callback_data='shared_topics')],
    ]
    return InlineKeyboardMarkup(keyboard)

def handle_menu_selection(update: Update, context: CallbackContext):
    """Handle inline menu button selections."""
    query = update.callback_query
    telegram_id = query.from_user.id
    selection = query.data

    if selection == 'balance':
        balance = get_user_balance(telegram_id)
        response_text = f"Your current balance is {balance} queries remaining."
        if balance < 5:
            response_text += "\n\nYou're running low on queries. Consider buying more to keep enjoying our service."
        query.answer()
        query.edit_message_text(text=response_text)
    elif selection == 'history':
        query.answer()
        history_text = fetch_user_history(telegram_id)
        query.edit_message_text(text=f"📜 *Your Recent History:*\n\n{history_text}", parse_mode='Markdown')
    elif selection == 'favorites':
        query.answer()
        favorites_text = fetch_user_favorites(telegram_id)
        query.edit_message_text(text=f"⭐️ *Your Favorites:*\n\n{favorites_text}", parse_mode='Markdown')
    elif selection == 'shared_topics':
        query.answer()
        shared_topics_text = fetch_shared_topics(telegram_id)
        query.edit_message_text(text=f"📢 *Shared Topics:*\n\n{shared_topics_text}", parse_mode='Markdown')
    else:
        query.answer("Unknown selection")

def handle_message(update: Update, context: CallbackContext):
    """Handle incoming text messages from users."""
    telegram_id = update.message.from_user.id
    user_query = update.message.text.strip()

    # Handle commands for saving favorites and bulk purchases
    if user_query.startswith("/save"):
        save_favorite(telegram_id, "Favorite content placeholder")
        update.message.reply_text("👍 Your response has been saved as a favorite!")
        return
    elif user_query.startswith("/buy10"):
        process_bulk_purchase(update, context, telegram_id, 10, 450)
        return
    elif user_query.startswith("/buy100"):
        process_bulk_purchase(update, context, telegram_id, 100, 3200)
        return

    # Check user balance before processing a query
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

    # Process the ChatGPT query normally
    response_text = process_chatgpt_query(user_query)
    update.message.reply_text(response_text)

    # Deduct one query credit and log the query in history
    update_user_balance(telegram_id, -1)
    log_history(telegram_id, user_query, response_text)

def process_bulk_purchase(update: Update, context: CallbackContext, telegram_id: int, queries: int, satoshi: int):
    """Handle bulk purchase commands for buying multiple queries."""
    invoice_data = create_invoice(amount=satoshi, memo=f"Bulk purchase of {queries} queries")
    payment_request = invoice_data.get("payment_request", "Error generating invoice")
    payment_hash = invoice_data.get("payment_hash", "")

    # Log the transaction in the database, including the number of queries purchased
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO transactions (telegram_id, invoice_id, payment_hash, amount, queries, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (telegram_id, payment_hash, payment_hash, satoshi, queries, "pending"))
    conn.commit()
    conn.close()

    qr_image = generate_qr_code(payment_request)

    purchase_message = (
        f"🛒 To purchase {queries} queries, please pay the following invoice:\n\n"
        f"`{payment_request}`\n\n"
        "📱 You can scan the QR code below to pay.\n\n"
        "Note: After payment, it may take up to 2 minutes for your new queries to be added."
    )
    update.message.reply_text(purchase_message, parse_mode='Markdown')
    update.message.reply_photo(photo=qr_image, caption="📱 Scan this QR code to pay.")

def payment_history(update: Update, context: CallbackContext):
    """Show the user their recent payment history."""
    telegram_id = update.message.from_user.id
    history = fetch_payment_history(telegram_id)
    update.message.reply_text(f"💳 *Your Payment History:*\n\n{history}", parse_mode='Markdown')

def user_stats(update: Update, context: CallbackContext):
    """Show the user their personal statistics."""
    telegram_id = update.message.from_user.id
    stats = fetch_user_stats(telegram_id)
    update.message.reply_text(f"📊 *Your Stats:*\n\n{stats}", parse_mode='Markdown')
