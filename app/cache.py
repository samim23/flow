# app/cache.py
"""
SQLite-based cache for build and upload operations.
Replaces the fragile pickle-based cache with a robust SQLite database.
"""

import sqlite3
import pickle
import logging
import json
from pathlib import Path
from typing import Optional, Any, Dict
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


class SQLiteCache:
    """Thread-safe SQLite cache for file hashes and build state."""
    
    def __init__(self, cache_dir: str = "cache", db_name: str = "cache.db"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / db_name
        self._init_db()
        
        # Check for and migrate from pickle if needed
        self._migrate_from_pickle()
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster prefix lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_key_prefix 
                ON cache(key)
            """)
            
            # Create metadata table for cache info
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level='DEFERRED'
        )
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        conn.execute("PRAGMA synchronous=NORMAL")  # Good balance of safety/speed
        try:
            yield conn
        finally:
            conn.close()
    
    def _migrate_from_pickle(self):
        """Migrate data from old pickle cache if it exists."""
        pickle_file = self.cache_dir / "filecache.pickle"
        backup_file = self.cache_dir / "filecache.pickle.migrated"
        
        if not pickle_file.exists():
            return
        
        # Check if we already migrated
        if backup_file.exists():
            return
        
        try:
            logger.info("Migrating from pickle cache to SQLite...")
            
            with open(pickle_file, 'rb') as f:
                old_cache = pickle.load(f)
            
            migrated_count = 0
            with self._get_connection() as conn:
                for key, value in old_cache.items():
                    # Convert value to string for storage
                    if isinstance(value, (list, dict)):
                        value_str = json.dumps(value)
                    else:
                        value_str = str(value)
                    
                    conn.execute(
                        """INSERT OR REPLACE INTO cache (key, value, updated_at) 
                           VALUES (?, ?, ?)""",
                        (key, value_str, datetime.now().isoformat())
                    )
                    migrated_count += 1
                
                # Store migration info
                conn.execute(
                    """INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)""",
                    ('migrated_from_pickle', datetime.now().isoformat())
                )
                conn.execute(
                    """INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)""",
                    ('migrated_entries', str(migrated_count))
                )
                
                conn.commit()
            
            # Rename old pickle file to mark as migrated
            pickle_file.rename(backup_file)
            logger.info(f"✓ Migrated {migrated_count} cache entries from pickle to SQLite")
            
        except Exception as e:
            logger.error(f"Error migrating pickle cache: {e}")
            # Don't fail - just continue with empty/partial cache
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT value FROM cache WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    return default
                
                value = row[0]
                
                # Try to parse as JSON for complex types
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
                    
        except Exception as e:
            logger.error(f"Cache get error for '{key}': {e}")
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """Set a value in the cache."""
        try:
            # Convert value to string
            if isinstance(value, (list, dict)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO cache (key, value, updated_at) 
                       VALUES (?, ?, ?)""",
                    (key, value_str, datetime.now().isoformat())
                )
                conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for '{key}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Cache delete error for '{key}': {e}")
            return False
    
    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys matching a prefix."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE key LIKE ?", (prefix + '%',)
                )
                deleted = cursor.rowcount
                conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Cache delete_prefix error for '{prefix}': {e}")
            return 0
    
    def keys(self, prefix: str = "") -> list:
        """Get all keys, optionally filtered by prefix."""
        try:
            with self._get_connection() as conn:
                if prefix:
                    cursor = conn.execute(
                        "SELECT key FROM cache WHERE key LIKE ?", (prefix + '%',)
                    )
                else:
                    cursor = conn.execute("SELECT key FROM cache")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Cache keys error: {e}")
            return []
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM cache WHERE key = ? LIMIT 1", (key,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Cache contains error for '{key}': {e}")
            return False
    
    def __getitem__(self, key: str) -> Any:
        """Dict-like access for getting values."""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
    
    def __setitem__(self, key: str, value: Any):
        """Dict-like access for setting values."""
        self.set(key, value)
    
    def __delitem__(self, key: str):
        """Dict-like access for deleting values."""
        self.delete(key)
    
    def clear(self) -> int:
        """Clear all cache entries."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM cache")
                cleared = cursor.rowcount
                conn.commit()
            logger.info(f"Cleared {cleared} cache entries")
            return cleared
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM cache")
                total = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE key LIKE 'build/%'"
                )
                build_files = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE key LIKE 'static:%'"
                )
                static_files = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE key LIKE 'page.html:%'"
                )
                page_cache = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE key LIKE 'tag:%'"
                )
                tag_cache = cursor.fetchone()[0]
                
                return {
                    'total_entries': total,
                    'build_files': build_files,
                    'static_files': static_files,
                    'page_cache': page_cache,
                    'tag_cache': tag_cache,
                    'db_path': str(self.db_path),
                    'db_size_mb': round(self.db_path.stat().st_size / (1024 * 1024), 2)
                }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {}


# Global cache instance
_cache_instance: Optional[SQLiteCache] = None


def get_cache() -> SQLiteCache:
    """Get or create the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SQLiteCache()
    return _cache_instance





