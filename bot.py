import logging
import threading
import time
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from config import TELEGRAM_TOKEN
from database import init_db, get_connection
from handlers import start, handle_menu_selection, handle_message, update_user_balance
from payments import check_payment
from config import TELEGRAM_TOKEN

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def check_pending_transactions(bot):
    """Periodically check pending transactions and credit user accounts if payment is confirmed."""
    while True:
        conn = get_connection()
        c = conn.cursor()
        # Fetch all pending transactions
        c.execute("SELECT id, telegram_id, payment_hash, amount, status FROM transactions WHERE status = 'pending'")
        pending_txns = c.fetchall()
        
        for txn in pending_txns:
            txn_id, telegram_id, payment_hash, amount, status = txn
            if check_payment(payment_hash):
                # Payment confirmed; update transaction status
                c.execute("UPDATE transactions SET status = 'completed' WHERE id = ?", (txn_id,))
                
                # Credit the user's account with purchased queries
                update_user_balance(telegram_id, amount)  # Adjust logic if needed for single/bulk
                conn.commit()
                
                # Send notification to the user
                try:
                    bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"✅ Thank you! Your payment has been received. "
                            f"Your account has been credited with additional queries. 🎉\n\n"
                            "You can now continue asking questions!"
                        )
                    )
                except Exception as e:
                    logger.error(f"Error sending message to {telegram_id}: {e}")
        
        conn.commit()
        conn.close()
        
        # Wait for 60 seconds before checking again
        time.sleep(60)

def main():
    # Initialize database
    init_db()

    # Create updater and dispatcher
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Register handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_menu_selection))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the bot with polling
    updater.start_polling()

    # Start background thread for checking pending transactions
    threading.Thread(target=check_pending_transactions, args=(updater.bot,), daemon=True).start()

    updater.idle()

if __name__ == '__main__':
    main()
