import logging
import threading
import time
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from database import init_db, get_connection
from handlers import (
    start, handle_message, payment_history,
    user_stats, handle_purchase_callback, update_user_balance
)
from payments import check_payment

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def check_pending_transactions(bot):
    """Periodically check pending transactions and credit user accounts if payment is confirmed."""
    while True:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, telegram_id, payment_hash, amount, queries, status FROM transactions WHERE status = 'pending'")
        pending_txns = c.fetchall()
        
        for txn in pending_txns:
            txn_id, telegram_id, payment_hash, amount, queries, status = txn
            if check_payment(payment_hash):
                c.execute("UPDATE transactions SET status = 'completed' WHERE id = ?", (txn_id,))
                # Use imported update_user_balance function with global lock in handlers.py
                update_user_balance(telegram_id, queries)
                conn.commit()
                try:
                    bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            f"✅ Thank you! Your payment has been received. "
                            f"Your account has been credited with {queries} additional queries. 🎉\n\n"
                            "You can now continue asking questions!"
                        )
                    )
                except Exception as e:
                    logger.error(f"Error sending message to {telegram_id}: {e}")
        
        conn.commit()
        conn.close()
        time.sleep(60)

def main():
    init_db()
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("paymenthistory", payment_history))
    dp.add_handler(CommandHandler("mystats", user_stats))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(handle_purchase_callback, pattern='^buy_'))

    updater.start_polling()
    threading.Thread(target=check_pending_transactions, args=(updater.bot,), daemon=True).start()
    updater.idle()

if __name__ == '__main__':
    main()
