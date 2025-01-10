from database import get_connection
import qrcode
import io

def fetch_user_history(telegram_id: int) -> str:
    """Retrieve the last 10 history entries for a user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT query, response, timestamp FROM history WHERE telegram_id = ? ORDER BY timestamp DESC LIMIT 10", (telegram_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "No history available."
    return "\n".join([f"{ts}: Q: {q}\nA: {a}" for q, a, ts in rows])

def fetch_user_favorites(telegram_id: int) -> str:
    """Retrieve the last 10 favorites for a user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT content, timestamp FROM favorites WHERE telegram_id = ? ORDER BY timestamp DESC LIMIT 10", (telegram_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "No favorites saved."
    return "\n".join([f"{ts}: {content}" for content, ts in rows])

def fetch_shared_topics(telegram_id: int) -> str:
    """Retrieve the last 10 shared topics for a user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT content, timestamp FROM shared_topics WHERE telegram_id = ? ORDER BY timestamp DESC LIMIT 10", (telegram_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "No shared topics yet."
    return "\n".join([f"{ts}: {content}" for content, ts in rows])

def generate_qr_code(data: str) -> io.BytesIO:
    """Generate a QR code image from a data string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    bio = io.BytesIO()
    bio.name = "invoice.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

def fetch_payment_history(telegram_id: int) -> str:
    """Retrieve the last 10 payment transactions for a user with query details."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT amount, queries, status, timestamp 
        FROM transactions 
        WHERE telegram_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 10
    """, (telegram_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "You haven't made any payments yet."
    history_lines = []
    for amount, queries, status, ts in rows:
        history_lines.append(f"{ts}: Amount {amount} satoshis for {queries} queries, Status: {status}")
    return "\n".join(history_lines)

def fetch_user_stats(telegram_id: int) -> str:
    """Retrieve statistics for a specific user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(amount) FROM transactions WHERE telegram_id = ? AND status = 'completed'", (telegram_id,))
    total_transactions, total_amount = c.fetchone()
    c.execute("SELECT SUM(queries) FROM transactions WHERE telegram_id = ? AND status = 'completed'", (telegram_id,))
    total_queries = c.fetchone()[0] or 0
    
    # Total searches made by the user
    c.execute("SELECT COUNT(*) FROM history WHERE telegram_id = ?", (telegram_id,))
    total_searches = c.fetchone()[0]
    
    conn.close()
    
    stats = [
        f"Total Completed Transactions: {total_transactions}",
        f"Total Amount Processed: {total_amount if total_amount else 0} satoshis",
        f"Total Queries Purchased: {total_queries}",
        f"Total Searches Made: {total_searches}"
    ]
    return "\n".join(stats)
