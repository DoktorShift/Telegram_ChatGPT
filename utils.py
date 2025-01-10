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
