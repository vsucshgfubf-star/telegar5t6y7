import sqlite3
from config import DB_NAME
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_name = DB_NAME
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Table for checked items
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS checked_items (
                    id TEXT PRIMARY KEY,
                    market_hash_name TEXT NOT NULL,
                    price REAL,
                    float REAL,
                    has_keychains INTEGER,
                    inspect_link TEXT,
                    check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table for user searches
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    skin_name TEXT NOT NULL,
                    charm_required INTEGER DEFAULT 0,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, skin_name)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    def item_exists(self, item_id):
        """Check if item already exists in database"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM checked_items WHERE id = ?', (item_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking item existence: {e}")
            return False
    
    def save_item(self, item_id, market_hash_name, price, float_val, has_keychains, inspect_link):
        """Save checked item to database"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO checked_items 
                (id, market_hash_name, price, float, has_keychains, inspect_link)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (item_id, market_hash_name, price, float_val, has_keychains, inspect_link))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving item: {e}")
            return False
    
    def add_search(self, user_id, skin_name, charm_required):
        """Add new search for user"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_searches (user_id, skin_name, charm_required)
                VALUES (?, ?, ?)
            ''', (user_id, skin_name, charm_required))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error adding search: {e}")
            return False
    
    def get_user_searches(self, user_id):
        """Get all searches for user"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, skin_name, charm_required FROM user_searches 
                WHERE user_id = ?
            ''', (user_id,))
            searches = cursor.fetchall()
            conn.close()
            return searches
        except Exception as e:
            logger.error(f"Error getting user searches: {e}")
            return []
    
    def delete_search(self, search_id):
        """Delete search by ID"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_searches WHERE id = ?', (search_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error deleting search: {e}")
            return False
    
    def get_all_searches(self):
        """Get all active searches"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, skin_name, charm_required FROM user_searches')
            searches = cursor.fetchall()
            conn.close()
            return searches
        except Exception as e:
            logger.error(f"Error getting all searches: {e}")
            return []
