from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie
import os
import html
import json
import random

from database import (
    update_user_theme,
    create_tables,
    create_user,
    get_user_by_email,
    update_user_profile,
    create_session,
    get_user_by_session_token,
    delete_session,
    create_deck,
    get_decks_by_user_id,
    get_deck_by_id_and_user,
    create_card,
    get_cards_by_deck_id,
    delete_deck,
    delete_card,
    update_deck,
    update_card,
    save_training_result,
    get_recent_training_results,
    get_daily_activity,
    get_user_training_summary,
    count_user_decks,
    count_user_cards,
)
from auth import hash_password, verify_password, generate_session_token

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))


class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/":
            self.handle_home()
        elif path == "/login":
            self.serve_file("login.html")
        elif path == "/register":
            self.serve_file("register.html")
        elif path == "/profile":
            self.handle_profile()
        elif path == "/logout":
            self.handle_logout_confirm()
        elif path == "/logout/confirm":
            self.handle_logout()
        elif path == "/cards":
            self.handle_cards_page()
        elif path == "/cards/create":
            self.handle_create_deck_page()
        elif path.startswith("/cards/") and path.endswith("/edit"):
            self.handle_edit_deck_page(path)
        elif path.startswith("/cards/") and "/edit-card/" in path:
            self.handle_edit_card_page(path)
        elif path.startswith("/cards/") and path.endswith("/add-card"):
            self.handle_add_card_page(path)
        elif path.startswith("/cards/") and path.endswith("/edit"):
            self.handle_edit_deck_page(path)
        elif path.startswith("/cards/") and "/edit-card/" in path:
            self.handle_edit_card_page(path)
        elif path.startswith("/cards/") and path.count("/") == 2:
            self.handle_deck_detail(path)
        elif path == "/dictionary":
            self.handle_dictionary_page()
        elif path.startswith("/dictionary/") and path.count("/") == 2:
            self.handle_dictionary_category(path)
        elif path == "/training":
            self.handle_training_page()
        elif path.startswith("/training/deck/") and path.count("/") == 3:
            self.handle_training_deck(path)
        elif path.startswith("/training/dictionary/") and path.count("/") == 3:
            self.handle_training_dictionary(path)
        elif path.startswith("/static/"):
            self.serve_static_file(path.lstrip("/"))
        else:
            self.send_error(404, "Page not found")

    def handle_training_result_save(self):
        user = self.get_current_user()

        if not user:
            self.send_response(401)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw_data = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        source_type = data.get("source_type", "")
        source_id = str(data.get("source_id", ""))
        source_title = data.get("source_title", "")
        total_words = int(data.get("total_words", 0))
        correct_answers = int(data.get("correct_answers", 0))
        wrong_answers = int(data.get("wrong_answers", 0))

        save_training_result(
            user["id"],
            source_type,
            source_id,
            source_title,
            total_words,
            correct_answers,
            wrong_answers
        )

        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

    def handle_delete_deck(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[2])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        success = delete_deck(deck_id, user["id"])

        if not success:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        self.redirect("/cards")
    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/register":
            self.handle_register()
        elif path == "/login":
            self.handle_login()
        elif path == "/cards/create":
            self.handle_create_deck()
        elif path.startswith("/cards/") and path.endswith("/add-card"):
            self.handle_add_card(path)
        elif path.startswith("/cards/") and path.endswith("/edit"):
            self.handle_edit_deck(path)
        elif path.startswith("/cards/") and "/edit-card/" in path:
            self.handle_edit_card(path)
        elif path.startswith("/cards/") and path.endswith("/edit"):
            self.handle_edit_deck(path)
        elif path.startswith("/cards/") and "/edit-card/" in path:
            self.handle_edit_card(path)
        elif path.startswith("/cards/") and path.endswith("/delete"):
            self.handle_delete_deck(path)
        elif path.startswith("/cards/") and "/delete-card/" in path:
            self.handle_delete_card(path)
        elif path == "/training/save-result":
            self.handle_training_result_save()
        elif path == "/profile/update":
            self.handle_profile_update()
        elif path == "/profile/theme":
            self.handle_theme_update()
        else:
            self.send_error(404, "Page not found")



    def handle_delete_card(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            parts = path.strip("/").split("/")
            deck_id = int(parts[1])
            card_id = int(parts[3])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        success = delete_card(card_id, deck_id, user["id"])

        if not success:
            self.send_html_message("Помилка", "Картку не знайдено або доступ заборонено.")
            return

        self.redirect(f"/cards/{deck_id}")

    def handle_edit_deck_page(self, path):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[2])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        deck = get_deck_by_id_and_user(deck_id, user["id"])
        if not deck:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        title = html.escape(deck["title"] or "")
        description = html.escape(deck["description"] or "")

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Редагувати набір | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
         <body>
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" class="active-link">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="profile-page">
                <section class="auth-card">
                    <h2>Редагувати набір</h2>

                    <form method="POST" action="/cards/{deck_id}/edit">
                        <input type="text" name="title" value="{title}" placeholder="Назва набору" required>
                        <textarea name="description" placeholder="Опис набору">{description}</textarea>
                        <button type="submit" class="btn primary">Зберегти зміни</button>
                        <a href="/cards/{deck_id}" class="btn secondary">Скасувати</a>
                    </form>
                </section>
                <section class="profile-edit-card">
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_edit_deck(self, path):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[2])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        form_data = self.get_form_data()
        title = form_data.get("title", [""])[0].strip()
        description = form_data.get("description", [""])[0].strip()

        if not title:
            self.send_html_message("Помилка", "Назва набору не може бути порожньою.")
            return

        success = update_deck(deck_id, user["id"], title, description)

        if not success:
            self.send_html_message("Помилка", "Не вдалося оновити набір.")
            return

        self.redirect(f"/cards/{deck_id}")

    def handle_edit_card_page(self, path):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return

        try:
            parts = path.strip("/").split("/")
            deck_id = int(parts[1])
            card_id = int(parts[3])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        deck = get_deck_by_id_and_user(deck_id, user["id"])
        if not deck:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        cards = get_cards_by_deck_id(deck_id)
        card = None
        for item in cards:
            if item["id"] == card_id:
                card = item
                break

        if not card:
            self.send_html_message("Помилка", "Картку не знайдено.")
            return

        word = html.escape(card["word"] or "")
        translation = html.escape(card["translation"] or "")
        example = html.escape(card["example"] or "")
        image_url = html.escape(card["image_url"] or "")

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Редагувати картку | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" class="active-link">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="profile-page">
                <section class="auth-card">
                    <h2>Редагувати картку</h2>

                    <form method="POST" action="/cards/{deck_id}/edit-card/{card_id}">
                        <input type="text" name="word" value="{word}" placeholder="Англійське слово" required>
                        <input type="text" name="translation" value="{translation}" placeholder="Переклад" required>
                        <input type="text" name="image_url" value="{image_url}" placeholder="Посилання на картинку">
                        <textarea name="example" placeholder="Приклад речення">{example}</textarea>

                        <button type="submit" class="btn primary">Зберегти зміни</button>
                        <a href="/cards/{deck_id}" class="btn secondary">Скасувати</a>
                    </form>
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_edit_card(self, path):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return

        try:
            parts = path.strip("/").split("/")
            deck_id = int(parts[1])
            card_id = int(parts[3])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        form_data = self.get_form_data()
        word = form_data.get("word", [""])[0].strip()
        translation = form_data.get("translation", [""])[0].strip()
        image_url = form_data.get("image_url", [""])[0].strip()
        example = form_data.get("example", [""])[0].strip()

        if not word or not translation:
            self.send_html_message("Помилка", "Слово і переклад є обов’язковими.")
            return

        success = update_card(card_id, deck_id, user["id"], word, translation, example, image_url)

        if not success:
            self.send_html_message("Помилка", "Не вдалося оновити картку.")
            return

        self.redirect(f"/cards/{deck_id}")

    def get_footer_html(self, is_guest=False):
        if is_guest:
            nav_links = """
                <a href="/">Головна</a>
                <a href="/login">Вхід</a>
                <a href="/register">Реєстрація</a>
            """
        else:
            nav_links = """
                <a href="/">Головна</a>
                <a href="/cards">Картки</a>
                <a href="/dictionary">Словник</a>
                <a href="/training">Тренування</a>
                <a href="/profile">Профіль</a>
            """

        return f"""
        <footer class="footer">
            <div class="footer-container">

                <div class="footer-brand">
                    <div class="footer-logo">
                        <img src="/static/images/logo.png" alt="FlashLearn logo">
                        <span>FlashLearn</span>
                    </div>

                    <p class="footer-text">
                        Сучасна платформа для вивчення англійської мови через
                        флешкарти, словники та інтерактивні тренування.
                    </p>
                </div>

                <div class="footer-links">
                    <h4>Навігація</h4>
                    {nav_links}
                </div>

                <div class="footer-links">
                    <h4>Можливості</h4>
                    <a href="/cards">Картки</a>
                    <a href="/dictionary">Словник</a>
                    <a href="/training">Тренування</a>
                </div>

                <div class="footer-right">
                    <div class="footer-badge">✨ Learn English красиво та легко</div>
                    <span>© 2026 FlashLearn. Усі права захищені.</span>
                </div>

            </div>
        </footer>
        """

    def get_header_html(self, active="home", is_guest=False):
        if is_guest:
            links = f"""
                <a href="/" class="{'active-link' if active == 'home' else ''}">Головна</a>
                <a href="/login" class="{'active-link' if active == 'login' else ''}">Вхід</a>
                <a href="/register" class="{'active-link' if active == 'register' else ''}">Реєстрація</a>
            """
        else:
            links = f"""
                <a href="/" class="{'active-link' if active == 'home' else ''}">Головна</a>
                <a href="/cards" class="{'active-link' if active == 'cards' else ''}">Картки</a>
                <a href="/dictionary" class="{'active-link' if active == 'dictionary' else ''}">Словник</a>
                <a href="/training" class="{'active-link' if active == 'training' else ''}">Тренування</a>
                <a href="/profile" class="{'active-link' if active == 'profile' else ''}">Профіль</a>
                <a href="/logout">Вийти</a>
            """

        return f"""
        <header class="header">
            <div class="container">
                <a href="/" class="logo">
                    <img src="/static/images/logo.png" alt="FlashLearn logo">
                    <span>FlashLearn</span>
                </a>

                <nav class="nav">
                    {links}
                </nav>
            </div>
        </header>
        """
    def handle_home(self):
        user = self.get_current_user()

        if user:
            username = html.escape(user["username"] or "")
            summary = get_user_training_summary(user["id"])
            total_words = summary["total_words"] if summary else 0

            progress_goal = 300
            progress_percent = min(round((total_words / progress_goal) * 100), 100)
            

            page_html = f"""
            <!DOCTYPE html>
            <html lang="uk">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Головна | FlashLearn</title>
                <link rel="stylesheet" href="/static/css/style.css">
            </head>
            <body class="{user['theme']}-theme">
                <header class="header">
                    <div class="container">
                        <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                        <nav class="nav">
                            <a href="/" class="active-link">Головна</a>
                            <a href="/cards">Картки</a>
                            <a href="/dictionary">Словник</a>
                            <a href="/training">Тренування</a>
                            <a href="/profile">Профіль</a>
                            <a href="/logout">Вийти</a>
                        </nav>
                    </div>
                </header>

                <main class="cute-member-page">
                    <section class="cute-member-hero">
                        <div class="cute-member-left">
                            <div class="cute-member-pill">👋 Особистий простір користувача</div>
                            <h1>Привіт, {username}! 👋</h1>
                            <p>
                                Чудовий день для навчання! Тут зібрані всі основні розділи:
                                картки, словник, тренування та профіль.
                            </p>

                            <div class="cute-member-actions">
                                <a href="/cards" class="btn primary">Перейти до карток</a>
                                <a href="/training" class="btn secondary">Почати тренування</a>
                            </div>
                        </div>

                        <div class="cute-member-right">
                            <img src="/static/images/cat.png" class="cute-member-cat" alt="cat">

                            <div class="cute-member-card-day">
                                <span>Картка дня</span>
                                <h3>confident</h3>
                                <p>впевнений</p>
                            </div>
                        </div>
                    </section>

                    <section class="cute-progress-row">
    <div class="cute-progress-card pastel-purple">
    <h3>Мій прогрес</h3>
    <strong>{total_words}/{progress_goal}</strong>
    <p>слів пройдено</p>
    <div class="cute-progress-line">
        <div style="width: {progress_percent}%;"></div>
    </div>
</div>

    <div class="cute-progress-card pastel-green">
        <h3>Словник</h3>
        <img src="/static/images/dictionary.png" alt="dictionary">
        <p>Готові теми</p>
    </div>

    <div class="cute-progress-card pastel-pink">
        <h3>Картки</h3>
        <img src="/static/images/book.png" alt="book">
        <p>Мої набори</p>
    </div>

    <div class="cute-progress-card pastel-yellow">
        <h3>Тренування</h3>
        <img src="/static/images/brain.png" alt="brain">
        <p>Перевірка знань</p>
    </div>
</section>

                   <section class="member-learning-path">
    <div class="section-heading">
        <div class="section-badge">Твій навчальний маршрут</div>
        <h2>Що можна зробити сьогодні?</h2>
        <p>Обери швидку дію та продовжуй навчання без зайвих переходів.</p>
    </div>

    <div class="member-action-grid">
        <a href="/cards/create" class="member-action-card">
            <span>✨</span>
            <h3>Створити новий набір</h3>
            <p>Додай слова, які хочеш вивчити саме зараз.</p>
        </a>

        <a href="/dictionary" class="member-action-card">
            <span>📖</span>
            <h3>Відкрити готовий словник</h3>
            <p>Обери тему та швидко поповни словниковий запас.</p>
        </a>

        <a href="/training" class="member-action-card">
            <span>🧠</span>
            <h3>Пройти тренування</h3>
            <p>Перевір себе та закріпи нові слова.</p>
        </a>
    </div>
</section>
                </main>

                {self.get_footer_html()}
            </body>
            </html>
            """
            self.send_html(page_html)
            return

        self.serve_file("index.html")

    def handle_register(self):
        form_data = self.get_form_data()

        username = form_data.get("username", [""])[0].strip()
        email = form_data.get("email", [""])[0].strip()
        password = form_data.get("password", [""])[0].strip()

        if not username or not email or not password:
            self.send_html_message("Помилка", "Усі поля мають бути заповнені.", True)
            return

        existing_user = get_user_by_email(email)
        if existing_user:
            self.send_html_message("Помилка", "Користувач з такою поштою вже існує.", True)
            return

        password_hash = hash_password(password)
        create_user(username, email, password_hash)

        self.send_html_message(
            "Успіх",
            "Реєстрація пройшла успішно. Тепер увійди у свій акаунт.",
            True,
            '<a href="/login" class="btn primary">Перейти до входу</a>'
        )

    def handle_login(self):
        form_data = self.get_form_data()

        email = form_data.get("email", [""])[0].strip()
        password = form_data.get("password", [""])[0].strip()

        if not email or not password:
            self.send_html_message("Помилка", "Введи пошту і пароль.", True)
            return

        user = get_user_by_email(email)

        if not user or not verify_password(password, user["password_hash"]):
            self.send_html_message("Помилка", "Неправильна пошта або пароль.", True)
            return

        session_token = generate_session_token()
        create_session(user["id"], session_token)

        self.send_response(302)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"session_token={session_token}; Path=/; HttpOnly")
        self.end_headers()

    def handle_profile(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        user_id = user["id"]
        username_raw = user["username"] if "username" in user.keys() else ""
        email_raw = user["email"] if "email" in user.keys() else ""
        avatar_url_raw = user["avatar_url"] if "avatar_url" in user.keys() else ""
        bio_raw = user["bio"] if "bio" in user.keys() else ""

        username = html.escape(username_raw or "")
        email = html.escape(email_raw or "")
        avatar_url = html.escape(avatar_url_raw or "")
        bio = html.escape(bio_raw or "")

        user_id = user["id"]

        decks_count = count_user_decks(user_id)
        cards_count = count_user_cards(user_id)
        summary = get_user_training_summary(user_id)
        recent_results = get_recent_training_results(user_id, 8)
        daily_activity = get_daily_activity(user_id, 7)

        total_sessions = summary["total_sessions"] if summary else 0
        total_words = summary["total_words"] if summary else 0
        total_correct = summary["total_correct"] if summary else 0
        total_wrong = summary["total_wrong"] if summary else 0
        avg_success = round(summary["avg_success"]) if summary else 0

        if avatar_url:
            avatar_html = f'<img src="{avatar_url}" alt="{username}" class="profile-avatar-image">'
        else:
            first_letter = username[:1].upper() if username else "U"
            avatar_html = f'<div class="profile-avatar-placeholder">{first_letter}</div>'

        recent_results_html = ""
        if recent_results:
            for result in recent_results:
                source_title = html.escape(result["source_title"] or "")
                source_type = html.escape(result["source_type"] or "")
                total = result["total_words"]
                correct = result["correct_answers"]
                wrong = result["wrong_answers"]
                percent = result["success_percent"]
                trained_at = html.escape(result["trained_at"] or "")

                source_label = "Мій набір" if source_type == "deck" else "Словник"

                recent_results_html += f"""
                <div class="result-card">
                    <div class="result-card-top">
                        <div>
                            <span class="result-source">{source_label}</span>
                            <h3>📚 {source_title}</h3>
                        </div>

                        <div class="result-percent">{percent}%</div>
                    </div>

                    <div class="result-stats">
                        <span>Слів: {total}</span>
                        <span>✅ {correct}</span>
                        <span>❌ {wrong}</span>
                    </div>

                    <div class="result-date">{trained_at}</div>
                </div>
                """
        else:
            recent_results_html = """
            <div class="profile-placeholder-item">
                Історія тренувань поки порожня. Пройди перше тренування, щоб тут з’явилися результати.
            </div>
            """

        activity_html = ""
        if daily_activity:
            for day in daily_activity:
                activity_date = html.escape(day["activity_date"] or "")
                trainings_count = day["trainings_count"]
                words_trained = day["words_trained"]
                correct_answers = day["correct_answers"]
                wrong_answers = day["wrong_answers"]

                activity_html += f"""
                <div class="activity-day-card">
                    <div class="activity-date">📅 {activity_date}</div>

                    <div class="activity-stats">
                        <div class="activity-item">
                            <span>Тренувань</span>
                            <strong>{trainings_count}</strong>
                        </div>

                        <div class="activity-item">
                            <span>Слів</span>
                            <strong>{words_trained}</strong>
                        </div>

                        <div class="activity-item success">
                            <span>Правильно</span>
                            <strong>{correct_answers}</strong>
                        </div>

                        <div class="activity-item error">
                            <span>Помилки</span>
                            <strong>{wrong_answers}</strong>
                        </div>
                    </div>
                </div>
                """
        else:
            activity_html = """
            <div class="profile-placeholder-item">
                Активність поки відсутня. Після перших тренувань тут з’явиться статистика по днях.
            </div>
            """
        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Профіль | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile" class="active-link">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="profile-dashboard-page">
                <section class="profile-hero-card">
                    <div class="profile-hero-left">
                        <div class="premium-chip">👤 Особистий кабінет</div>
                        <h1>{username}</h1>
                        <p class="profile-email-text">{email}</p>
                        <p class="profile-bio-text">
                            {bio if bio else "Додай короткий опис про себе, щоб зробити профіль більш живим і персональним."}
                        </p>
                    </div>

                    <div class="profile-hero-right">
                        {avatar_html}
                    </div>
                </section>

               <section class="profile-stats-grid">
    <div class="profile-stat-card">
        <span>Набори</span>
        <strong>{decks_count}</strong>
    </div>
    <div class="profile-stat-card">
        <span>Картки</span>
        <strong>{cards_count}</strong>
    </div>
    <div class="profile-stat-card">
        <span>Тренування</span>
        <strong>{total_sessions}</strong>
    </div>
    <div class="profile-stat-card">
        <span>Успішність</span>
        <strong>{avg_success}%</strong>
    </div>
    <div class="profile-stat-card">
        <span>Слів пройдено</span>
        <strong>{total_words}</strong>
    </div>
    <div class="profile-stat-card">
        <span>Правильні</span>
        <strong>{total_correct}</strong>
    </div>
    <div class="profile-stat-card">
        <span>Неправильні</span>
        <strong>{total_wrong}</strong>
    </div>
</section>
<section class="profile-edit-card">
    <div class="section-badge">Тема сайту</div>
    <h2>Оформлення</h2>

    <form method="POST" action="/profile/theme" class="theme-form">
        <button type="submit" name="theme" value="light" class="btn secondary">
            ☀️ Світла тема
        </button>

        <button type="submit" name="theme" value="dark" class="btn primary">
            🌙 Темна тема
        </button>
    </form>
</section>
                <section class="profile-edit-card">
                    <div class="section-badge">Редагування профілю</div>
                    <h2>Оновити профіль</h2>

                    <form method="POST" action="/profile/update" enctype="multipart/form-data" class="profile-edit-form">
                        <input type="text" name="username" value="{username}" placeholder="Ім'я користувача" required>

                        <label class="profile-upload-label">
                            <span>Обрати фото профілю</span>
                            <input type="file" name="avatar" accept="image/*">
                        </label>

                        <textarea name="bio" placeholder="Коротко про себе">{bio_raw or ""}</textarea>

                        <button type="submit" class="btn primary">Зберегти зміни</button>
                    </form>
                </section>
                <section class="profile-sections-grid">
                    <div class="profile-section-card">
                        <div class="section-badge">Активність</div>
                        <h2>Останні дні</h2>
                        <div class="profile-activity-grid">
                            {activity_html}
                        </div>
                    </div>

                    <div class="profile-section-card">
                        <div class="section-badge">Історія тренувань</div>
                        <h2>Останні результати</h2>
                        <div class="profile-history-list">
                            {recent_results_html}
                        </div>
                    </div>
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_theme_update(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        form_data = self.get_form_data()
        theme = form_data.get("theme", ["light"])[0]

        if theme not in ["light", "dark"]:
            theme = "light"

        update_user_theme(user["id"], theme)
        self.redirect("/profile")

    def handle_profile_update(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            self.send_html_message("Помилка", "Неправильний формат форми")
            return

        try:
            boundary = content_type.split("boundary=")[1].encode()
        except IndexError:
            self.send_html_message("Помилка", "Не знайдено boundary у формі")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        parts = body.split(b"--" + boundary)

        username = ""
        bio = ""
        avatar_filename = None
        avatar_data = None

        for part in parts:
            if b'name="username"' in part:
                try:
                    username = part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n-").decode("utf-8").strip()
                except Exception:
                    pass

            elif b'name="bio"' in part:
                try:
                    bio = part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n-").decode("utf-8").strip()
                except Exception:
                    pass

            elif b'name="avatar"' in part and b"filename=" in part:
                try:
                    header, file_data = part.split(b"\r\n\r\n", 1)
                    file_data = file_data.rstrip(b"\r\n-")

                    filename_part = header.split(b'filename="', 1)[1]
                    filename = filename_part.split(b'"', 1)[0].decode("utf-8").strip()

                    if filename:
                        safe_filename = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
                        avatar_filename = f"user_{user['id']}_{safe_filename}"
                        avatar_data = file_data
                except Exception:
                    pass

        if not username:
            username = user["username"]

        avatar_url = user["avatar_url"] if "avatar_url" in user.keys() else ""

        if avatar_filename and avatar_data:
            os.makedirs("static/uploads", exist_ok=True)
            file_path = os.path.join("static", "uploads", avatar_filename)

            with open(file_path, "wb") as f:
                f.write(avatar_data)

            avatar_url = f"/static/uploads/{avatar_filename}"

        update_user_profile(user["id"], username, avatar_url, bio)
        self.redirect("/profile")

    def handle_cards_page(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        decks = get_decks_by_user_id(user["id"])

        decks_html = ""
        if decks:
            emojis = ["🌍", "📘", "🧠", "✨", "🎯", "💬", "🚀", "📚"]
            for index, deck in enumerate(decks):
                description = deck["description"] if deck["description"] else "Опис поки що не додано."
                title = html.escape(deck["title"] or "")
                description = html.escape(description)
                emoji = emojis[index % len(emojis)]

                decks_html += f"""
                <div class="deck-card-wrap">
                    <a href="/cards/{deck['id']}" class="deck-link-card">
                        <div class="deck-premium-card">
                            <div class="deck-premium-top">
                                <div class="deck-premium-icon">{emoji}</div>
                                <div class="profile-badge">Набір карток</div>
                            </div>
                            <h3>{deck['title']}</h3>
                            <p>{description}</p>
                            <div class="deck-premium-bottom">
                                <span>Відкрити набір →</span>
                            </div>
                        </div>
                    </a>
                    <a href="/cards/{deck['id']}/edit" class="btn secondary">Редагувати набір</a>

                    <form method="POST" action="/cards/{deck['id']}/delete" class="delete-inline-form"
                          onsubmit="return confirm('Ти справді хочеш видалити цей набір разом з усіма картками?');">
                        <button type="submit" class="btn danger-btn">Видалити набір</button>
                    </form>
                </div>
                """
        else:
            decks_html = """
            <div class="empty-premium-card">
                <div class="empty-premium-emoji">💜</div>
                <h3>У тебе ще немає наборів</h3>
                <p>Створи свій перший набір карток і почни будувати власний словниковий простір.</p>
            </div>
            """

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Картки | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" class="active-link">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="cards-premium-page">
    <section class="cards-premium-hero">

        <div class="cards-premium-left">
            <div class="premium-chip">📚 Мої навчальні набори</div>

            <h1>Твої картки</h1>

            <p>
                Створюй тематичні набори, додавай слова,
                приклади й перетворюй навчання на приємний процес.
            </p>

            <a href="/cards/create" class="btn primary">
                Створити набір ✨
            </a>
        </div>

        <div class="cards-premium-plant">
            <img src="/static/images/plant.png" alt="Plant">
        </div>

    </section>

                <div class="search-filter-box">
    <input 
        type="text" 
        id="cards-search" 
        class="search-filter-input" 
        placeholder="Пошук набору за назвою або описом..."
    >
</div>
<section class="decks-premium-grid" id="cards-grid">
    {decks_html}
</section>

<script>
    const cardsSearch = document.getElementById("cards-search");
    const deckCards = document.querySelectorAll("#cards-grid .deck-card-wrap");

    cardsSearch.addEventListener("input", function () {{
        const value = this.value.toLowerCase().trim();

        deckCards.forEach(card => {{
            const text = card.textContent.toLowerCase();
            card.style.display = text.includes(value) ? "block" : "none";
        }});
    }});
</script>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_create_deck_page(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Створити набір | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" class="active-link">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="profile-page">
                <section class="auth-card">
                    <h2>Створення нового набору</h2>
                    <form method="POST" action="/cards/create">
                        <input type="text" name="title" placeholder="Назва набору" required>
                        <textarea name="description" placeholder="Короткий опис набору"></textarea>
                        <button type="submit" class="btn primary">Зберегти набір</button>
                    </form>
                </section>
            </main>
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_create_deck(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        form_data = self.get_form_data()
        title = form_data.get("title", [""])[0].strip()
        description = form_data.get("description", [""])[0].strip()

        if not title:
            self.send_html_message("Помилка", "Назва набору не може бути порожньою.")
            return

        create_deck(user["id"], title, description)
        self.redirect("/cards")

    def handle_deck_detail(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[2])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        deck = get_deck_by_id_and_user(deck_id, user["id"])

        if not deck:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        cards = get_cards_by_deck_id(deck_id)

        cards_html = ""
        if cards:
            for card in cards:
                word = html.escape(card["word"] or "")
                translation = html.escape(card["translation"] or "")
                example = html.escape(card["example"] or "")
                image_url = html.escape(card["image_url"] or "")

                image_html = ""
                if image_url:
                    image_html = f'<img src="{image_url}" alt="{word}" class="flip-card-image">'

                example_html = ""
                if example:
                    example_html = f'<p class="flip-card-example"><strong>Приклад:</strong> {example}</p>'

                cards_html += f"""
                <article class="flip-card-item">
                    <div class="flip-card" onclick="this.classList.toggle('is-flipped')">
                        <div class="flip-card-inner">
                            <div class="flip-card-front">
                                <div class="profile-badge">English</div>
                                <div class="flip-card-front-emoji">✨</div>
                                <h3>{word}</h3>
                                <p>Натисни, щоб перевернути</p>
                            </div>

                            <div class="flip-card-back">
                                <div class="profile-badge">Українська</div>
                                <h3>{translation}</h3>
                                {image_html}
                                {example_html}
                            </div>
                        </div>
                    </div>
                    <a href="/cards/{deck_id}/edit-card/{card['id']}" class="btn secondary">Редагувати картку</a>
                    <form method="POST" action="/cards/{deck_id}/delete-card/{card['id']}" class="delete-inline-form"
                          onsubmit="return confirm('Ти справді хочеш видалити цю картку?');">
                        <button type="submit" class="btn danger-btn">Видалити картку</button>
                    </form>
                </article>
                """
        else:
            cards_html = """
            <div class="empty-premium-card">
                <div class="empty-premium-emoji">🪄</div>
                <h3>У цьому наборі ще немає карток</h3>
                <p>Додай першу картку, щоб набір став живим і наповненим.</p>
            </div>
            """

        deck_title = html.escape(deck["title"] or "")
        deck_description = html.escape(deck["description"] or "Опис поки що не додано.")

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{deck_title} | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" class="active-link">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="cards-premium-page">
                <section class="cards-premium-hero">
                    <div>
                        <div class="premium-chip">🗂️ Деталі набору</div>
                        <h1>{deck_title}</h1>
                        <p>{deck_description}</p>
                    </div>
                    <a href="/cards/{deck_id}/add-card" class="btn primary">Додати картку 💜</a>
                </section>

                <section class="flip-cards-grid">
                    {cards_html}
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_add_card_page(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[2])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        deck = get_deck_by_id_and_user(deck_id, user["id"])

        if not deck:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        deck_title = html.escape(deck["title"] or "")

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Додати картку | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" class="active-link">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="profile-page">
                <section class="auth-card">
                    <h2>Додати картку до набору</h2>
                    <p style="text-align:center; margin-bottom:20px; color:#6e5f8d;">
                        Набір: <strong>{deck_title}</strong>
                    </p>

                    <form method="POST" action="/cards/{deck_id}/add-card">
                        <input type="text" name="word" placeholder="Англійське слово" required>
                        <input type="text" name="translation" placeholder="Переклад українською" required>
                        <input type="text" name="image_url" placeholder="Посилання на картинку">
                        <textarea name="example" placeholder="Приклад речення"></textarea>
                        <button type="submit" class="btn primary">Зберегти картку</button>
                    </form>
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_add_card(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[2])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        deck = get_deck_by_id_and_user(deck_id, user["id"])

        if not deck:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        form_data = self.get_form_data()
        word = form_data.get("word", [""])[0].strip()
        translation = form_data.get("translation", [""])[0].strip()
        image_url = form_data.get("image_url", [""])[0].strip()
        example = form_data.get("example", [""])[0].strip()

        if not word or not translation:
            self.send_html_message("Помилка", "Слово і переклад є обов’язковими полями.")
            return

        create_card(deck_id, word, translation, example, image_url)
        self.redirect(f"/cards/{deck_id}")

    def load_dictionary_data(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        dictionary_path = os.path.join(base_dir, "dictionary.json")

        if not os.path.exists(dictionary_path):
            print("DICTIONARY FILE NOT FOUND:", dictionary_path)
            return {"categories": []}

        with open(dictionary_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def handle_dictionary_page(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        data = self.load_dictionary_data()
        categories = data.get("categories", [])

        categories_html = ""
        if categories:
            for category in categories:
                category_name = html.escape(category.get("name", "Без назви"))
                category_slug = html.escape(category.get("id", ""))
                category_icon = html.escape(category.get("icon", "📚"))
                category_description = html.escape(category.get("description", "Опис відсутній"))
                words_count = len(category.get("words", []))

                categories_html += f"""
                <a href="/dictionary/{category_slug}" class="deck-link-card">
                    <div class="deck-premium-card">
                        <div class="deck-premium-top">
                            <div class="deck-premium-icon">{category_icon}</div>
                            <div class="profile-badge">Тема словника</div>
                        </div>
                        <h3>{category_name}</h3>
                        <p>{category_description}</p>
                        <div class="deck-premium-bottom">
                            <span>{words_count} слів →</span>
                        </div>
                    </div>
                </a>
                """
        else:
            categories_html = """
            <div class="empty-premium-card">
                <div class="empty-premium-emoji">📚</div>
                <h3>Словник поки порожній</h3>
                <p>Додай теми у dictionary.json, щоб вони з’явилися тут.</p>
            </div>
            """

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Словник | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav nav-glass">
                        <a href="/">Головна</a>
                        <a href="/cards">Картки</a>
                        <a href="/dictionary" class="active-link">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="cards-premium-page">
                <section class="cards-premium-hero">
                    <div>
                        <div class="premium-chip">📖 Готовий словник</div>
                        <h1>Тематичні папки зі словами</h1>
                        <p>
                            Обирай тему, відкривай готові слова, дивись переклад, картинки
                            та приклади речень у красивому картковому форматі.
                        </p>
                    </div>
                </section>

                <section class="decks-premium-grid">
                    {categories_html}
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_dictionary_category(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            category_id = path.split("/")[2]
        except IndexError:
            self.send_error(404, "Page not found")
            return

        data = self.load_dictionary_data()
        categories = data.get("categories", [])

        selected_category = None
        for category in categories:
            if category.get("id") == category_id:
                selected_category = category
                break

        if not selected_category:
            self.send_html_message("Помилка", "Тему словника не знайдено.")
            return

        category_name = html.escape(selected_category.get("name", "Без назви"))
        category_icon = html.escape(selected_category.get("icon", "📚"))
        category_description = html.escape(selected_category.get("description", "Опис відсутній"))
        words = selected_category.get("words", [])

        words_html = ""
        if words:
            for word_item in words:
                word = html.escape(word_item.get("word", ""))
                translation = html.escape(word_item.get("translation", ""))
                sticker = html.escape(word_item.get("sticker", "✨"))
                example = html.escape(word_item.get("example", ""))

                example_html = ""
                if example:
                    example_html = f'<p class="dictionary-flip-example"><strong>Приклад:</strong> {example}</p>'

                words_html += f"""
                <article class="dictionary-flip-card-item">
                    <div class="dictionary-flip-card" onclick="this.classList.toggle('is-flipped')">
                        <div class="dictionary-flip-inner">
                            <div class="dictionary-flip-front">
                                <div class="profile-badge">English</div>
                                <div class="dictionary-front-mini">{category_icon}</div>
                                <h3>{word}</h3>
                                <p>Натисни, щоб перевернути</p>
                            </div>

                            <div class="dictionary-flip-back">
                                <div class="profile-badge">Українська</div>
                                <div class="dictionary-sticker">{sticker}</div>
                                <h3>{translation}</h3>
                                {example_html}
                            </div>
                        </div>
                    </div>
                </article>
                """
        else:
            words_html = """
            <div class="empty-premium-card">
                <div class="empty-premium-emoji">🪄</div>
                <h3>У цій темі ще немає слів</h3>
                <p>Наповни dictionary.json, щоб слова з’явилися тут.</p>
            </div>
            """

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{category_name} | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav nav-glass">
                        <a href="/">Головна</a>
                        <a href="/cards">Картки</a>
                        <a href="/dictionary" class="active-link">Словник</a>
                        <a href="/training">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="cards-premium-page">
                <section class="cards-premium-hero">
                    <div>
                        <div class="premium-chip">{category_icon} Тема словника</div>
                        <h1>{category_name}</h1>
                        <p>{category_description}</p>
                    </div>

                    <a href="/dictionary" class="btn secondary">← До всіх тем</a>
                </section>

                <div class="search-filter-box">
    <input 
        type="text" 
        id="words-search" 
        class="search-filter-input" 
        placeholder="Пошук слова або перекладу..."
    >
</div>

<section class="dictionary-flip-grid" id="words-grid">
    {words_html}
</section>

<script>
    const wordsSearch = document.getElementById("words-search");
    const wordCards = document.querySelectorAll("#words-grid .dictionary-flip-card-item");

    wordsSearch.addEventListener("input", function () {{
        const value = this.value.toLowerCase().trim();

        wordCards.forEach(card => {{
            const text = card.textContent.toLowerCase();

            if (text.includes(value)) {{
                card.style.display = "block";
            }} else {{
                card.style.display = "none";
            }}
        }});
    }});
</script>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_training_page(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        decks = get_decks_by_user_id(user["id"])
        data = self.load_dictionary_data()
        categories = data.get("categories", [])

        my_decks_html = ""
        if decks:
            for deck in decks:
                title = html.escape(deck["title"] or "Без назви")
                description = html.escape(deck["description"] or "Опис поки що не додано.")
                my_decks_html += f"""
                <a href="/training/deck/{deck['id']}?shuffle=1" class="deck-link-card">
                    <div class="training-mode-card">
                        <div class="training-mode-top">
                            <div class="training-mode-icon">📚</div>
                            <div class="profile-badge">Мій набір</div>
                        </div>
                        <h3>{title}</h3>
                        <p>{description}</p>
                        <div class="training-mode-bottom">
                            <span>Почати тренування →</span>
                        </div>
                    </div>
                </a>
                """
        else:
            my_decks_html = """
            <div class="empty-premium-card">
                <div class="empty-premium-emoji">🪄</div>
                <h3>У тебе ще немає наборів</h3>
                <p>Створи набір карток, щоб тренувати власні слова.</p>
            </div>
            """

        dictionary_html = ""
        if categories:
            for category in categories:
                category_name = html.escape(category.get("name", "Без назви"))
                category_id = html.escape(category.get("id", ""))
                category_icon = html.escape(category.get("icon", "📖"))
                category_description = html.escape(category.get("description", "Опис відсутній"))
                words_count = len(category.get("words", []))

                dictionary_html += f"""
                <a href="/training/dictionary/{category_id}?shuffle=1" class="deck-link-card">
                    <div class="training-mode-card">
                        <div class="training-mode-top">
                            <div class="training-mode-icon">{category_icon}</div>
                            <div class="profile-badge">Словник</div>
                        </div>
                        <h3>{category_name}</h3>
                        <p>{category_description}</p>
                        <div class="training-mode-bottom">
                            <span>{words_count} слів →</span>
                        </div>
                    </div>
                </a>
                """
        else:
            dictionary_html = """
            <div class="empty-premium-card">
                <div class="empty-premium-emoji">📖</div>
                <h3>Словник порожній</h3>
                <p>Додай теми у dictionary.json, щоб тренувати слова зі словника.</p>
            </div>
            """

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Тренування | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training" class="active-link">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="training-hub-page">
               <section class="training-hub-hero training-hub-hero-single">
    <div class="training-hub-left">
        <div class="premium-chip">⚡ Інтерактивний режим</div>
        <h1>Обери формат тренування</h1>
        <p>
            Тренуй свої власні картки або готові слова зі словника.
            Усе оформлено так, щоб навчання було швидким, красивим і зручним.
        </p>
    </div>
</section>

                <section class="training-section-block">
                    <div class="training-section-title">
                        <h2>Мої набори</h2>
                        <p>Тут ти можеш тренувати слова, які додала самостійно.</p>
                    </div>
                    <div class="decks-premium-grid">
                        {my_decks_html}
                    </div>
                </section>

                <section class="training-section-block">
                    <div class="training-section-title">
                        <h2>Словник</h2>
                        <p>Готові тематичні добірки для швидкого старту та повторення.</p>
                    </div>
                    <div class="decks-premium-grid">
                        {dictionary_html}
                    </div>
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_training_deck(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            deck_id = int(path.split("/")[3])
        except (IndexError, ValueError):
            self.send_error(404, "Page not found")
            return

        deck = get_deck_by_id_and_user(deck_id, user["id"])

        if not deck:
            self.send_html_message("Помилка", "Набір не знайдено або доступ заборонено.")
            return

        cards = get_cards_by_deck_id(deck_id)

        training_cards = []
        card_stickers = ["📘", "💬", "🧠", "✨", "🎯", "💙", "🚀", "🔹"]

        for index, card in enumerate(cards):
            training_cards.append({
                "front": card["word"] or "",
                "back": card["translation"] or "",
                "hint": card["example"] or "",
                "sticker": card_stickers[index % len(card_stickers)]
            })

        query = parse_qs(urlparse(self.path).query)
        shuffle = query.get("shuffle", ["0"])[0] == "1"

        if shuffle:
            random.shuffle(training_cards)

        title = html.escape(deck["title"] or "Набір")
        back_link = "/training"
        self.render_training_session(title, training_cards, back_link, "deck", deck_id)

    def handle_training_dictionary(self, path):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        try:
            category_id = path.split("/")[3]
        except IndexError:
            self.send_error(404, "Page not found")
            return

        data = self.load_dictionary_data()
        categories = data.get("categories", [])

        selected_category = None
        for category in categories:
            if category.get("id") == category_id:
                selected_category = category
                break

        if not selected_category:
            self.send_html_message("Помилка", "Тему словника не знайдено.")
            return

        words = selected_category.get("words", [])
        training_cards = []
        for word_item in words:
            training_cards.append({
                "front": word_item.get("word", ""),
                "back": word_item.get("translation", ""),
                "hint": word_item.get("example", ""),
                "sticker": word_item.get("sticker", "✨")
            })

        query = parse_qs(urlparse(self.path).query)
        shuffle = query.get("shuffle", ["0"])[0] == "1"

        if shuffle:
            random.shuffle(training_cards)

        title = html.escape(selected_category.get("name", "Словник"))
        back_link = "/training"
        self.render_training_session(title, training_cards, back_link, "dictionary", category_id)

    def render_training_session(self, title, cards, back_link, source_type="unknown", source_id="0", mode="write"):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        if not cards:
            self.send_html_message("Помилка", "У цьому режимі поки немає слів для тренування.")
            return

        normalized_cards = []
        for item in cards:
            normalized_cards.append({
                "front": item.get("front", ""),
                "back": item.get("back", ""),
                "hint": item.get("hint", ""),
                "sticker": item.get("sticker", "✨")
            })

        cards_json = json.dumps(normalized_cards, ensure_ascii=False)

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Тренування — {title}</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards">Картки</a>
                        <a href="/dictionary">Словник</a>
                        <a href="/training" class="active-link">Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="training-lux-page">
                <section class="training-lux-hero">
                    <div class="training-lux-hero-left">
                        <div class="premium-chip">🧠 Інтерактивне тренування</div>
                        <h1>{title}</h1>
                        <p>
                            Введи правильний переклад українською, перевір себе
                            та переглянь результат після завершення тренування.
                        </p>
                    </div>

                    <div class="training-lux-hero-right">
                        <a href="{back_link}" class="btn secondary">← Назад</a>
                    </div>
                </section>

                <section class="training-lux-layout" id="training-layout">
                    <div class="training-lux-topbar">
                        <div class="training-lux-progress-card">
                            <div class="training-lux-progress-head">
                                <span>Прогрес</span>
                                <strong id="training-counter">1 / {len(normalized_cards)}</strong>
                            </div>

                            <div class="training-progress-bar training-progress-bar-lux">
                                <div id="training-progress-fill" class="training-progress-fill"></div>
                            </div>
                        </div>
                        <div class="training-mode-switch">
    <button type="button" class="training-mode-btn" id="write-mode-btn">
        ✍️ Вписати
    </button>

    <button type="button" class="training-mode-btn" id="choice-mode-btn">
        🔘 4 варіанти
    </button>

    <button type="button" class="training-mode-btn" id="mistakes-mode-btn">
        🔁 Помилки
    </button>
</div>
                        <div class="training-lux-mini-stats">
                            <div class="training-lux-mini-box">
                                <span>Режим</span>
                                <strong id="mode-label"></strong>
                            </div>
                            <div class="training-lux-mini-box">
                                <span>Джерело</span>
                                <strong>{title}</strong>
                            </div>
                        </div>
                    </div>

                    <div class="training-lux-main-card" id="training-quiz-card">
                        <div class="training-lux-card-top">
                            <div class="profile-badge">English</div>
                            <div class="training-lux-word-chip">Введи переклад</div>
                        </div>

                        <div class="training-lux-word-icon-wrap">
                            <div class="training-front-icon training-front-icon-lux">📘</div>
                        </div>

                        <h2 id="training-front-text" class="training-lux-main-word"></h2>
                        <p class="training-lux-subtext">
                            Подумай над перекладом і введи його в поле нижче
                        </p>

                        <div class="training-answer-block training-answer-block-lux">
                            <label for="training-answer" class="training-label">Твоя відповідь</label>
                            <input
                                id="training-answer"
                                class="training-input training-input-lux"
                                type="text"
                                placeholder="Напиши переклад українською"
                                autocomplete="off"
                            >
                        </div>
                        <div id="training-choices" style="display:none;" class="training-choices-grid"></div>
                        <div id="training-result" class="training-result training-result-lux"></div>

                        <div id="training-correct-block" class="training-correct-block training-correct-block-lux">
                            <div class="training-lux-answer-head">
                                <div class="training-sticker" id="training-sticker"></div>
                                <div>
                                    <span class="training-lux-answer-label">Правильна відповідь</span>
                                    <h3 id="training-back-text"></h3>
                                </div>
                            </div>
                            <p id="training-hint"></p>
                        </div>
                    </div>

                    <div class="training-controls training-controls-lux" id="training-controls">
                        <button class="btn secondary training-btn" id="prev-btn" type="button">← Назад</button>
                        <button class="btn primary training-btn training-check-btn" id="check-btn" type="button">Перевірити</button>
                        <button class="btn secondary training-btn training-btn-disabled" id="next-btn" type="button" disabled>Далі →</button>
                    </div>

                    <div class="training-summary-card training-summary-card-lux" id="training-summary-card" style="display: none;">
                        <div class="profile-badge">Результати тренування</div>
                        <div class="training-summary-emoji">🏆</div>
                        <h2>Тренування завершено</h2>
                        <p class="training-summary-text-lux">
                            Подивись свій результат і за потреби пройди цей набір ще раз,
                            щоб краще закріпити лексику.
                        </p>

                        <div class="training-summary-grid">
                            <div class="training-summary-box">
                                <span>Усього слів</span>
                                <strong id="summary-total">0</strong>
                            </div>
                            <div class="training-summary-box">
                                <span>Правильно</span>
                                <strong id="summary-correct">0</strong>
                            </div>
                            <div class="training-summary-box">
                                <span>Неправильно</span>
                                <strong id="summary-wrong">0</strong>
                            </div>
                            <div class="training-summary-box">
                                <span>Успішність</span>
                                <strong id="summary-percent">0%</strong>
                            </div>
                        </div>

                        <div class="training-summary-actions">
                            <button class="btn primary training-btn" id="restart-btn" type="button">Пройти ще раз</button>
                            <a href="{back_link}" class="btn secondary training-btn">До вибору тренування</a>
                        </div>
                    </div>
                </section>
            </main>

            {self.get_footer_html()}

            <script>
    let trainingCards = {cards_json};
    let originalCards = [...trainingCards];
    let mode = "{mode}";
    let currentIndex = 0;
    let checkedIndexes = new Set();
    let mistakeCards = [];
    let correctCount = 0;
    let wrongCount = 0;
    let selectedChoice = "";

    const counter = document.getElementById("training-counter");
    const progressFill = document.getElementById("training-progress-fill");
    const frontText = document.getElementById("training-front-text");
    const backText = document.getElementById("training-back-text");
    const sticker = document.getElementById("training-sticker");
    const hint = document.getElementById("training-hint");
    const answerInput = document.getElementById("training-answer");
    const resultBlock = document.getElementById("training-result");
    const correctBlock = document.getElementById("training-correct-block");
    const choicesBlock = document.getElementById("training-choices");
    const modeLabel = document.getElementById("mode-label");

    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const checkBtn = document.getElementById("check-btn");
    const restartBtn = document.getElementById("restart-btn");

    const trainingQuizCard = document.getElementById("training-quiz-card");
    const trainingControls = document.getElementById("training-controls");
    const trainingSummaryCard = document.getElementById("training-summary-card");

    const summaryTotal = document.getElementById("summary-total");
    const summaryCorrect = document.getElementById("summary-correct");
    const summaryWrong = document.getElementById("summary-wrong");
    const summaryPercent = document.getElementById("summary-percent");

    function normalizeText(text) {{
        return (text || "")
            .toLowerCase()
            .trim()
            .replace(/\\s+/g, " ")
            .replace(/[.,!?;:]/g, "");
    }}

    function shuffleArray(array) {{
        return [...array].sort(() => Math.random() - 0.5);
    }}

    function setMode(newMode) {{
        mode = newMode;
        currentIndex = 0;
        checkedIndexes = new Set();
        mistakeCards = [];
        correctCount = 0;
        wrongCount = 0;

        trainingQuizCard.style.display = "flex";
        trainingControls.style.display = "flex";
        trainingSummaryCard.style.display = "none";

        renderCard();
    }}

    function buildChoices(correctAnswer) {{
        const allAnswers = originalCards
            .map(card => card.back)
            .filter(answer => answer && answer !== correctAnswer);

        const wrongAnswers = shuffleArray(allAnswers).slice(0, 3);
        const options = shuffleArray([correctAnswer, ...wrongAnswers]);

        choicesBlock.innerHTML = "";

        options.forEach(option => {{
            const button = document.createElement("button");
            button.type = "button";
            button.className = "choice-btn";
            button.textContent = option;

            button.addEventListener("click", () => {{
                selectedChoice = option;

                document.querySelectorAll(".choice-btn").forEach(btn => {{
                    btn.classList.remove("choice-btn-active");
                }});

                button.classList.add("choice-btn-active");
            }});

            choicesBlock.appendChild(button);
        }});
    }}

    function renderCard() {{
        const item = trainingCards[currentIndex];

        selectedChoice = "";

        frontText.textContent = item.front || "";
        backText.textContent = item.back || "";
        sticker.textContent = item.sticker || "✨";
        hint.textContent = item.hint || "";

        answerInput.value = "";
        resultBlock.textContent = "";
        resultBlock.className = "training-result training-result-lux";
        correctBlock.style.display = "none";

        nextBtn.disabled = true;
        nextBtn.classList.add("training-btn-disabled");

        counter.textContent = `${{currentIndex + 1}} / ${{trainingCards.length}}`;
        const progressPercent = ((currentIndex + 1) / trainingCards.length) * 100;
        progressFill.style.width = progressPercent + "%";

        if (mode === "choice") {{
            modeLabel.textContent = "Вибір з 4 варіантів";
            answerInput.parentElement.style.display = "none";
            choicesBlock.style.display = "grid";
            checkBtn.style.display = "inline-block";
            buildChoices(item.back);
        }} else {{
            modeLabel.textContent = "Письмова відповідь";
            answerInput.parentElement.style.display = "flex";
            choicesBlock.style.display = "none";
            choicesBlock.innerHTML = "";
            checkBtn.style.display = "inline-block";
        }}
    }}

    function checkAnswer() {{
    if (checkedIndexes.has(currentIndex)) {{
        return;
    }}

    const item = trainingCards[currentIndex];
    const correctAnswer = normalizeText(item.back);

    let userAnswer = "";
    let shownUserAnswer = "";

    if (mode === "choice") {{
        userAnswer = normalizeText(selectedChoice);
        shownUserAnswer = selectedChoice;

        if (!userAnswer) {{
            resultBlock.innerHTML = "<div class='training-result-card warning'>⚠️ Обери один варіант відповіді</div>";
            resultBlock.className = "training-result training-result-lux";
            return;
        }}
    }} else {{
        userAnswer = normalizeText(answerInput.value);
        shownUserAnswer = answerInput.value;

        if (!userAnswer) {{
            resultBlock.innerHTML = "<div class='training-result-card warning'>✍️ Спочатку введи відповідь</div>";
            resultBlock.className = "training-result training-result-lux";
            return;
        }}
    }}

    checkedIndexes.add(currentIndex);

    if (userAnswer === correctAnswer) {{
        resultBlock.innerHTML = `
            <div class="training-result-card success">
                <div class="training-result-icon">✅</div>
                <div>
                    <h3>Правильно!</h3>
                    <p>Твоя відповідь: <strong>${{shownUserAnswer}}</strong></p>
                </div>
            </div>
        `;
        correctCount++;
    }} else {{
        resultBlock.innerHTML = `
            <div class="training-result-card error">
                <div class="training-result-icon">❌</div>
                <div>
                    <h3>Неправильно</h3>
                    <p>Твоя відповідь: <strong>${{shownUserAnswer}}</strong></p>
                </div>
            </div>
        `;
        wrongCount++;
        mistakeCards.push(item);
    }}

    correctBlock.style.display = "flex";
    nextBtn.disabled = false;
    nextBtn.classList.remove("training-btn-disabled");
}}
    function goNext() {{
        if (currentIndex < trainingCards.length - 1) {{
            currentIndex++;
            renderCard();
        }} else {{
            showSummary();
        }}
    }}

    function repeatMistakes() {{
        if (mistakeCards.length === 0) {{
            alert("Помилок поки немає 🎉");
            return;
        }}

        trainingCards = [...mistakeCards];
        currentIndex = 0;
        checkedIndexes = new Set();
        mistakeCards = [];
        correctCount = 0;
        wrongCount = 0;

        trainingQuizCard.style.display = "flex";
        trainingControls.style.display = "flex";
        trainingSummaryCard.style.display = "none";

        renderCard();
    }}

    function showSummary() {{
        trainingQuizCard.style.display = "none";
        trainingControls.style.display = "none";
        trainingSummaryCard.style.display = "block";

        const total = trainingCards.length;
        const percent = total > 0 ? Math.round((correctCount / total) * 100) : 0;

        summaryTotal.textContent = total;
        summaryCorrect.textContent = correctCount;
        summaryWrong.textContent = wrongCount;
        summaryPercent.textContent = percent + "%";

        fetch("/training/save-result", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json"
            }},
            body: JSON.stringify({{
                source_type: "{source_type}",
                source_id: "{source_id}",
                source_title: "{title}",
                total_words: total,
                correct_answers: correctCount,
                wrong_answers: wrongCount
            }})
        }});
    }}

    function restartTraining() {{
        trainingCards = [...originalCards];
        currentIndex = 0;
        checkedIndexes = new Set();
        mistakeCards = [];
        correctCount = 0;
        wrongCount = 0;

        trainingQuizCard.style.display = "flex";
        trainingControls.style.display = "flex";
        trainingSummaryCard.style.display = "none";

        renderCard();
    }}

    checkBtn.addEventListener("click", checkAnswer);
    nextBtn.addEventListener("click", goNext);
    restartBtn.addEventListener("click", restartTraining);

    prevBtn.addEventListener("click", () => {{
        if (currentIndex > 0) {{
            currentIndex--;
            renderCard();
        }}
    }});

    answerInput.addEventListener("keydown", (event) => {{
        if (event.key === "Enter") {{
            event.preventDefault();
            checkAnswer();
        }}
    }});
document.getElementById("write-mode-btn").addEventListener("click", () => {{
    setMode("write");
}});

document.getElementById("choice-mode-btn").addEventListener("click", () => {{
    setMode("choice");
}});

document.getElementById("mistakes-mode-btn").addEventListener("click", () => {{
    repeatMistakes();
}});

renderCard();
</script>
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_placeholder_page(self, title, message):
        user = self.get_current_user()

        if not user:
            self.redirect("/login")
            return

        active_cards = 'class="active-link"' if title == "Картки" else ""
        active_dictionary = 'class="active-link"' if title == "Словник" else ""
        active_training = 'class="active-link"' if title == "Тренування" else ""

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title} | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="{user['theme']}-theme">
            <header class="header">
                <div class="container">
                    <div class="logo">
    <img src="/static/images/logo.png" alt="logo">
    <span>FlashLearn</span>
</div>
                    <nav class="nav">
                        <a href="/">Головна</a>
                        <a href="/cards" {active_cards}>Картки</a>
                        <a href="/dictionary" {active_dictionary}>Словник</a>
                        <a href="/training" {active_training}>Тренування</a>
                        <a href="/profile">Профіль</a>
                        <a href="/logout">Вийти</a>
                    </nav>
                </div>
            </header>

            <main class="profile-page">
                <section class="profile-card">
                    <div class="profile-badge">{title}</div>
                    <h1>{title}</h1>
                    <p>{message}</p>
                </section>
            </main>

            {self.get_footer_html()}
        </body>
        </html>
        """
        self.send_html(page_html)

    def handle_logout_confirm(self):
        user = self.get_current_user()

        if not user:
            self.redirect("/")
            return

        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Вихід | FlashLearn</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>

        <body class="{user['theme']}-theme">

            {self.get_header_html()}

            <main class="logout-page">
                <section class="logout-card">

                    <div class="logout-icon">👋</div>

                    <div class="premium-chip">
                        Підтвердження виходу
                    </div>

                    <h1>Вийти з акаунта?</h1>

                    <p>
                        Ти справді хочеш завершити поточну сесію?
                        Після виходу потрібно буде знову увійти в акаунт.
                    </p>

                    <div class="logout-actions">
                        <a href="/" class="btn secondary">Скасувати</a>

                        <a href="/logout/confirm" class="btn primary">
                            Так, вийти
                        </a>
                    </div>

                </section>
            </main>

            {self.get_footer_html()}

        </body>
        </html>
        """

        self.send_html(page_html)

    def handle_logout(self):
        session_token = self.get_session_token()

        if session_token:
            delete_session(session_token)

        self.send_response(302)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"session_token={session_token}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()

    def get_current_user(self):
        session_token = self.get_session_token()

        if not session_token:
            return None

        return get_user_by_session_token(session_token)

    def get_session_token(self):
        cookie_header = self.headers.get("Cookie")

        if not cookie_header:
            return None

        cookie = SimpleCookie()
        cookie.load(cookie_header)

        if "session_token" in cookie:
            return cookie["session_token"].value

        return None

    def get_form_data(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_data = self.rfile.read(content_length).decode("utf-8")
        return parse_qs(raw_data)

    def serve_file(self, filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, filepath)

        if not os.path.exists(full_path):
            self.send_error(404, "File not found")
            return

        with open(full_path, "rb") as file:
            content = file.read()

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content)

    def serve_static_file(self, filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        full_path = os.path.join(base_dir, filepath)
        
        if not os.path.exists(full_path):
            filename = os.path.basename(filepath)
            full_path = os.path.join(base_dir, filename)
        
        if not os.path.exists(full_path):
            self.send_error(404, "Static file not found")
            return

        content_type = "text/plain"
        if filepath.endswith(".css"):
            content_type = "text/css"
        elif filepath.endswith(".js"):
            content_type = "application/javascript"
        elif filepath.endswith(".png"):
            content_type = "image/png"
        elif filepath.endswith(".jpg") or filepath.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif filepath.endswith(".svg"):
            content_type = "image/svg+xml"
        elif filepath.endswith(".webp"):
            content_type = "image/webp"

        with open(full_path, "rb") as file:
            content = file.read()

        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.end_headers()
        self.wfile.write(content)

    def send_html_message(self, title, message, is_guest=False, extra_html=""):
        page_html = f"""
        <!DOCTYPE html>
        <html lang="uk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body>
            <div class="auth-page">
                <div class="auth-card">
                    <h2>{title}</h2>
                    <p style="text-align:center; margin-bottom:20px; color:#6e5f8d;">
                        {message}
                    </p>
                    <div style="display:flex; justify-content:center; gap:12px; flex-wrap:wrap;">
                        {extra_html}
                        <a href="/" class="btn secondary">На головну</a>
                    </div>
                </div>
            </div>

            {self.get_footer_html(is_guest)}
        </body>
        </html>
        """
        self.send_html(page_html)

    def send_html(self, page_html):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page_html.encode("utf-8"))

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


def run_server():
    create_tables()
    server = HTTPServer((HOST, PORT), MyHandler)
    print(f"Server started: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
