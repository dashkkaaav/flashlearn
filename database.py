import sqlite3
import os

DB_PATH = "instance/flashcards.db"


def get_connection():
    os.makedirs("instance", exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            avatar_url TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            theme TEXT DEFAULT 'light'
        )
    """)

    cursor.execute("PRAGMA table_info(users)")
    columns = [column["name"] for column in cursor.fetchall()]

    if "theme" not in columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN theme TEXT DEFAULT 'light'
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            translation TEXT NOT NULL,
            example TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deck_id) REFERENCES decks(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_title TEXT NOT NULL,
            total_words INTEGER NOT NULL DEFAULT 0,
            correct_answers INTEGER NOT NULL DEFAULT 0,
            wrong_answers INTEGER NOT NULL DEFAULT 0,
            success_percent INTEGER NOT NULL DEFAULT 0,
            trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_date TEXT NOT NULL,
            trainings_count INTEGER NOT NULL DEFAULT 0,
            words_trained INTEGER NOT NULL DEFAULT 0,
            correct_answers INTEGER NOT NULL DEFAULT 0,
            wrong_answers INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, activity_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()


def create_user(username, email, password_hash):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO users (username, email, password_hash)
        VALUES (?, ?, ?)
    """, (username, email, password_hash))

    connection.commit()
    connection.close()


def get_user_by_email(email):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE email = ?
    """, (email,))

    user = cursor.fetchone()
    connection.close()
    return user


def get_user_by_id(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (user_id,))

    user = cursor.fetchone()
    connection.close()
    return user

def create_session(user_id, session_token):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO sessions (user_id, session_token)
        VALUES (?, ?)
    """, (user_id, session_token))

    connection.commit()
    connection.close()


def get_user_by_session_token(session_token):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT users.*
        FROM sessions
        JOIN users ON sessions.user_id = users.id
        WHERE sessions.session_token = ?
    """, (session_token,))

    user = cursor.fetchone()
    connection.close()
    return user


def delete_session(session_token):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM sessions
        WHERE session_token = ?
    """, (session_token,))

    connection.commit()
    connection.close()


def create_deck(user_id, title, description):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO decks (user_id, title, description)
        VALUES (?, ?, ?)
    """, (user_id, title, description))

    connection.commit()
    connection.close()


def get_decks_by_user_id(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM decks
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))

    decks = cursor.fetchall()
    connection.close()
    return decks


def get_deck_by_id_and_user(deck_id, user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM decks
        WHERE id = ? AND user_id = ?
    """, (deck_id, user_id))

    deck = cursor.fetchone()
    connection.close()
    return deck


def count_user_decks(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM decks
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()
    connection.close()
    return result["total"] if result else 0


def create_card(deck_id, word, translation, example, image_url):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO cards (deck_id, word, translation, example, image_url)
        VALUES (?, ?, ?, ?, ?)
    """, (deck_id, word, translation, example, image_url))

    connection.commit()
    connection.close()


def get_cards_by_deck_id(deck_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM cards
        WHERE deck_id = ?
        ORDER BY id DESC
    """, (deck_id,))

    cards = cursor.fetchall()
    connection.close()
    return cards


def count_user_cards(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(cards.id) AS total
        FROM cards
        JOIN decks ON cards.deck_id = decks.id
        WHERE decks.user_id = ?
    """, (user_id,))

    result = cursor.fetchone()
    connection.close()
    return result["total"] if result else 0


def save_training_result(user_id, source_type, source_id, source_title, total_words, correct_answers, wrong_answers):
    success_percent = 0
    if total_words > 0:
        success_percent = round((correct_answers / total_words) * 100)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO training_results (
            user_id,
            source_type,
            source_id,
            source_title,
            total_words,
            correct_answers,
            wrong_answers,
            success_percent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        source_type,
        source_id,
        source_title,
        total_words,
        correct_answers,
        wrong_answers,
        success_percent
    ))

    cursor.execute("""
        INSERT INTO daily_activity (
            user_id,
            activity_date,
            trainings_count,
            words_trained,
            correct_answers,
            wrong_answers
        )
        VALUES (
            ?,
            DATE('now', 'localtime'),
            1,
            ?,
            ?,
            ?
        )
        ON CONFLICT(user_id, activity_date)
        DO UPDATE SET
            trainings_count = trainings_count + 1,
            words_trained = words_trained + excluded.words_trained,
            correct_answers = correct_answers + excluded.correct_answers,
            wrong_answers = wrong_answers + excluded.wrong_answers
    """, (
        user_id,
        total_words,
        correct_answers,
        wrong_answers
    ))

    connection.commit()
    connection.close()


def get_recent_training_results(user_id, limit=10):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM training_results
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))

    results = cursor.fetchall()
    connection.close()
    return results


def get_daily_activity(user_id, limit=30):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM daily_activity
        WHERE user_id = ?
        ORDER BY activity_date DESC
        LIMIT ?
    """, (user_id, limit))

    activity = cursor.fetchall()
    connection.close()
    return activity


def get_user_training_summary(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_sessions,
            COALESCE(SUM(total_words), 0) AS total_words,
            COALESCE(SUM(correct_answers), 0) AS total_correct,
            COALESCE(SUM(wrong_answers), 0) AS total_wrong,
            COALESCE(AVG(success_percent), 0) AS avg_success
        FROM training_results
        WHERE user_id = ?
    """, (user_id,))

    summary = cursor.fetchone()
    connection.close()
    return summary

def update_user_profile(user_id, username, avatar_url, bio):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET username = ?, avatar_url = ?, bio = ?
        WHERE id = ?
    """, (username, avatar_url, bio, user_id))

    connection.commit()
    connection.close()
def delete_deck(deck_id, user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id FROM decks
        WHERE id = ? AND user_id = ?
    """, (deck_id, user_id))
    deck = cursor.fetchone()

    if not deck:
        connection.close()
        return False

    cursor.execute("""
        DELETE FROM cards
        WHERE deck_id = ?
    """, (deck_id,))

    cursor.execute("""
        DELETE FROM decks
        WHERE id = ? AND user_id = ?
    """, (deck_id, user_id))

    connection.commit()
    connection.close()
    return True


def delete_card(card_id, deck_id, user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT cards.id
        FROM cards
        JOIN decks ON cards.deck_id = decks.id
        WHERE cards.id = ? AND cards.deck_id = ? AND decks.user_id = ?
    """, (card_id, deck_id, user_id))
    card = cursor.fetchone()

    if not card:
        connection.close()
        return False

    cursor.execute("""
        DELETE FROM cards
        WHERE id = ? AND deck_id = ?
    """, (card_id, deck_id))

    connection.commit()
    connection.close()
    return True
def update_deck(deck_id, user_id, title, description):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE decks
        SET title = ?, description = ?
        WHERE id = ? AND user_id = ?
    """, (title, description, deck_id, user_id))

    connection.commit()
    updated = cursor.rowcount
    connection.close()

    return updated > 0

def update_card(card_id, deck_id, user_id, word, translation, example, image_url):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE cards
        SET word = ?, translation = ?, example = ?, image_url = ?
        WHERE id = ?
        AND deck_id = ?
        AND deck_id IN (
            SELECT id FROM decks WHERE user_id = ?
        )
    """, (word, translation, example, image_url, card_id, deck_id, user_id))
    connection.commit()
    updated = cursor.rowcount
    connection.close()
    return updated > 0

def update_user_theme(user_id, theme):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET theme = ?
        WHERE id = ?
    """, (theme, user_id))

    connection.commit()
    connection.close()
