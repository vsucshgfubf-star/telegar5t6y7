import sqlite3
import logging
from config import DB_NAME

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file):
        """Initialize database connection"""
        self.db_file = db_file
        self.create_tables()
        logger.info(f"✅ Database initialized: {db_file}")
    
    def create_tables(self):
        """Create necessary tables"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Users searches table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    skin_name TEXT NOT NULL,
                    charm_required INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, skin_name)
                )
            ''')
            
            # Processed items table (to avoid duplicates)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_items (
                    item_id TEXT PRIMARY KEY,
                    market_hash_name TEXT,
                    price REAL,
                    float_value REAL,
                    keychains_count INTEGER,
                    inspect_link TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ Tables created")
        except Exception as e:
            logger.error(f"❌ Error creating tables: {e}")
            raise
    
    def add_search(self, user_id, skin_name, charm_required):
        """Add user search"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_searches (user_id, skin_name, charm_required)
                VALUES (?, ?, ?)
            ''', (user_id, skin_name, charm_required))
            conn.commit()
            conn.close()
            logger.info(f"✅ Search added: {skin_name}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"⚠️ Search already exists: {skin_name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error adding search: {e}")
            return False
    
    def delete_search(self, search_id):
        """Delete user search"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_searches WHERE id = ?', (search_id,))
            conn.commit()
            conn.close()
            logger.info(f"✅ Search deleted: {search_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting search: {e}")
            return False
    
    def get_user_searches(self, user_id):
        """Get all searches for user"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, skin_name, charm_required FROM user_searches WHERE user_id = ?',
                (user_id,)
            )
            searches = cursor.fetchall()
            conn.close()
            return searches
        except Exception as e:
            logger.error(f"❌ Error getting searches: {e}")
            return []
    
    def get_all_searches(self):
        """Get all searches from all users"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, skin_name, charm_required FROM user_searches')
            searches = cursor.fetchall()
            conn.close()
            return searches
        except Exception as e:
            logger.error(f"❌ Error getting all searches: {e}")
            return []
    
    def item_exists(self, item_id):
        """Check if item already processed"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM processed_items WHERE item_id = ?', (item_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"❌ Error checking item: {e}")
            return False
    
    def save_item(self, item_id, market_hash_name, price, float_value, keychains_count, inspect_link):
        """Save processed item"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO processed_items 
                (item_id, market_hash_name, price, float_value, keychains_count, inspect_link)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (item_id, market_hash_name, price, float_value, keychains_count, inspect_link))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error saving item: {e}")
            return False
