import aiomysql
from datetime import datetime, date
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await aiomysql.create_pool(
            host=os.getenv('MYSQL_HOST'),
            port=int(os.getenv('MYSQL_PORT')),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            db=os.getenv('MYSQL_DB'),
            autocommit=True
        )

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def init_db(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        telegram_id BIGINT NOT NULL UNIQUE,
                        username VARCHAR(100),
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        text TEXT NOT NULL,
                        reminder_time TIME NOT NULL,
                        reminder_date DATE NOT NULL,
                        job_id VARCHAR(36) NOT NULL UNIQUE,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)

    async def get_or_create_user(self, telegram_id: int, username: str = None, 
                               first_name: str = None, last_name: str = None) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT id FROM users WHERE telegram_id = %s",
                    (telegram_id,)
                )
                user = await cursor.fetchone()
                
                if not user:
                    await cursor.execute(
                        """INSERT INTO users 
                        (telegram_id, username, first_name, last_name) 
                        VALUES (%s, %s, %s, %s)""",
                        (telegram_id, username, first_name, last_name)
                    )
                    return cursor.lastrowid
                return user[0]

    async def add_reminder(self, user_id: int, text: str, 
                         reminder_time: str, reminder_date: date, 
                         job_id: str) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        """INSERT INTO reminders 
                        (user_id, text, reminder_time, reminder_date, job_id) 
                        VALUES (%s, %s, %s, %s, %s)""",
                        (user_id, text, reminder_time, reminder_date, job_id)
                    )
                    return True
                except Exception as e:
                    print(f"Error adding reminder: {e}")
                    return False

    async def get_user_reminders(self, user_id: int) -> list:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """SELECT * FROM reminders 
                    WHERE user_id = %s AND is_active = TRUE
                    ORDER BY reminder_date, reminder_time""",
                    (user_id,)
                )
                return await cursor.fetchall()

    async def deactivate_reminder(self, job_id: str) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE reminders SET is_active = FALSE WHERE job_id = %s",
                    (job_id,)
                )
                return cursor.rowcount > 0

    async def get_active_reminders_count(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM reminders WHERE is_active = TRUE "
                    "AND (reminder_date > CURDATE() OR "
                    "(reminder_date = CURDATE() AND reminder_time > CURTIME()))"
                )
                return (await cursor.fetchone())[0]

db = Database()