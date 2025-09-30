import sqlite3
import os
import time


class NodesDB:
    def __init__(self, db_path="data/nodes.db"):
        """Initialize SQLite database for nodes data.

        Args:
            db_path: Path to the SQLite database file. Defaults to data/nodes.db
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Create table if it doesn't exist
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                ip TEXT PRIMARY KEY,
                node_id TEXT,
                kaspad TEXT,
                discovered_at INTEGER
            )
        """
        )
        self.conn.commit()

    def upsert_node(self, ip, node_id, kaspad):
        """Insert or update a node with current timestamp.

        Args:
            ip: IP address with port (e.g., "1.2.3.4:16111")
            node_id: Node ID
            kaspad: Kaspad version string
        """
        current_time = int(time.time())
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO nodes (ip, node_id, kaspad, discovered_at)
            VALUES (?, ?, ?, ?)
            """,
            (ip, node_id, kaspad, current_time),
        )
        self.conn.commit()

    def get_all_nodes(self, max_age_days=None):
        """Get all nodes, optionally filtered by age.

        Args:
            max_age_days: If provided, only return nodes discovered within this many days

        Returns:
            Dictionary of nodes in the format: {ip: {id, kaspad, discovered_at}}
        """
        if max_age_days is not None:
            cutoff_time = int(time.time()) - (max_age_days * 24 * 60 * 60)
            self.cursor.execute(
                """
                SELECT ip, node_id, kaspad, discovered_at
                FROM nodes
                WHERE discovered_at >= ?
                ORDER BY ip
                """,
                (cutoff_time,),
            )
        else:
            self.cursor.execute(
                """
                SELECT ip, node_id, kaspad, discovered_at
                FROM nodes
                ORDER BY ip
                """
            )

        nodes = {}
        for row in self.cursor.fetchall():
            ip, node_id, kaspad, discovered_at = row
            nodes[ip] = {
                "id": node_id,
                "kaspad": kaspad,
                "discovered_at": discovered_at,
            }

        return nodes

    def get_latest_update_time(self):
        """Get the timestamp of the most recently discovered node.

        Returns:
            Integer timestamp or current time if no nodes exist
        """
        self.cursor.execute("SELECT MAX(discovered_at) FROM nodes")
        result = self.cursor.fetchone()[0]
        return result if result is not None else int(time.time())

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        if hasattr(self, "conn"):
            self.conn.close()
