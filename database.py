import sqlite3

def get_connection():
    """
    Create and return a new database connection with WAL mode and increased timeout.
    WAL mode allows concurrent reads and writes, reducing "database is locked" errors.
    Increased timeout allows more time for transactions to complete.
    """
    conn = sqlite3.connect('botdata.db', timeout=60, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """Initialize database tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()
    # Users table to store balance
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    balance INTEGER DEFAULT 0
                 )''')
    # History table to store query and responses
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    query TEXT,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    # Favorites table to store favorite responses
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    # Shared topics table for shared content
    c.execute('''CREATE TABLE IF NOT EXISTS shared_topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    # Transactions table for tracking payments with queries purchased
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    invoice_id TEXT,
                    payment_hash TEXT,
                    amount INTEGER,
                    queries INTEGER,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    conn.commit()
    conn.close()
