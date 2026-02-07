import sqlite3


def create_db(db_path: str = "data.db") -> None:
    """Создаёт базу и таблицы для бота.

    Запускать один раз при развёртывании.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cats (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            am_time TEXT NOT NULL,
            peak INTEGER NOT NULL,
            pm_time TEXT NOT NULL,
            PRIMARY KEY (chat_id, name)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS measure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            tag TEXT NOT NULL,
            FOREIGN KEY (chat_id, name)
                REFERENCES cats (chat_id, name)
                ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_db()
