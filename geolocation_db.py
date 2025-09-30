import sqlite3
import os


class GeolocationDB:
    def __init__(self, db_path="data/geolocation.db"):
        """Initialize SQLite database for geolocation data.

        Args:
            db_path: Path to the SQLite database file. Defaults to data/geolocation.db
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Create table if it doesn't exist
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS geolocation (
                ip TEXT PRIMARY KEY,
                location TEXT
            )
        """
        )
        self.conn.commit()

    def get(self, ip):
        """Get geolocation for an IP address.

        Args:
            ip: IP address to lookup

        Returns:
            Location string (e.g., "48.8000,12.3167") or None if not found
        """
        self.cursor.execute("SELECT location FROM geolocation WHERE ip = ?", (ip,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def set(self, ip, loc):
        """Set geolocation for an IP address.

        Args:
            ip: IP address
            loc: Location string (e.g., "48.8000,12.3167")
        """
        self.cursor.execute(
            "INSERT OR REPLACE INTO geolocation (ip, location) VALUES (?, ?)", (ip, loc)
        )
        self.conn.commit()

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        if hasattr(self, "conn"):
            self.conn.close()
