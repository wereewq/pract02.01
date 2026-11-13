from datetime import date, timedelta, datetime, timezone
import hashlib
import jwt
from sqlmodel import Session, select
from app.models.entities import (
    User, Store, Product, Stock, Supplier, Customer, DiscountCard, Sale, SaleItem, Supply, SupplyItem
)

SECRET_KEY = "knigograd-secret-key-2026"
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed

def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "login": user.login,
        "role": user.role,
        "full_name": user.full_name,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

def seed_initial_data(session: Session):
    if session.exec(select(User)).first():
        return

    # 1. Пользователи из Сценария тестов (СТ)
    users = [
        User(login="admin_book", password_hash=hash_password("AdminBook2026!"), full_name="Смирнов Алексей Викторович", role="Администратор"),
        User(login="manager_book", password_hash=hash_password("Manager2026!"), full_name="Козлова Елена Сергеевна", role="Менеджер"),
        User(login="cashier_book", password_hash=hash_password("Cashier2026!"), full_name="Волкова Анна Дмитриевна", role="Кассир"),
        User(login="director_book", password_hash=hash_password("Director2026!"), full_name="Морозов Игорь Николаевич", role="Руководитель"),
    ]
    session.add_all(users)
    session.commit()

    # 2. Три магазина сети ООО «КнигоГрад»
    stores = [
        Store(name="Магазин №1 (Центральный)", address="ул. Тверская, д. 12"),
        Store(name="Магазин №2 (Северный)", address="Ленинградский пр-т, д. 45"),
        Store(name="Магазин №3 (Южный)", address="ул. Профсоюзная, д. 88"),
    ]
    session.add_all(stores)
    session.commit()

    # 3. Товары (книги)
    products = [
        Product(title="Мастер и Маргарита", author="Булгаков Михаил Афанасьевич", category="Классика", price=650.00, isbn="9785170908301"),
        Product(title="Война и мир (Том 1-2)", author="Толстой Лев Николаевич", category="Классика", price=890.00, isbn="9785389062566"),
        Product(title="Преступление и наказание", author="Достоевский Фёдор Михайлович", category="Классика", price=540.00, isbn="9785041166748"),
        Product(title="Пикник на обочине", author="Стругацкий Аркадий Натанович", category="Фантастика", price=590.00, isbn="9785171124564"),
        Product(title="Дюна", author="Герберт Фрэнк", category="Фантастика", price=1150.00, isbn="9785171204129"),
        Product(title="Грокаем алгоритмы", author="Бхаргава Адитья", category="IT и программирование", price=1450.00, isbn="9785446109234"),
    ]
    session.add_all(products)
    session.commit()

    # 4. Остатки по 3 магазинам (включая позиции с низким и нулевым остатком для проверки дашборда)
    stock_matrix = [
        (1, 1, 18), (1, 2, 12), (1, 3, 9),
        (2, 1, 3),  (2, 2, 7),  (2, 3, 2),   # низкий остаток
        (3, 1, 15), (3, 2, 4),  (3, 3, 11),
        (4, 1, 2),  (4, 2, 0),  (4, 3, 6),   # низкий и нулевой остаток
        (5, 1, 10), (5, 2, 8),  (5, 3, 5),
        (6, 1, 1),  (6, 2, 3),  (6, 3, 0),   # дефицит
    ]
    for pid, sid, qty in stock_matrix:
        session.add(Stock(product_id=pid, store_id=sid, quantity=qty))
    session.commit()

    # 5. Поставщики
    suppliers = [
        Supplier(name="Издательство «Эксмо»", contact_name="Петров Сергей", phone="+74954116886", email="opt@eksmo.ru", address="г. Москва, ул. Зорге, д. 1"),
        Supplier(name="Издательская группа «Азбука-Аттикус»", contact_name="Соколова Мария", phone="+74959337601", email="sales@atticus-group.ru", address="г. Москва, пр-д Воскресенские ворота, д. 1А"),
    ]
    session.add_all(suppliers)
    session.commit()

    # 6. Клиенты и дисконтные карты (активная и просроченная для тестов)
    c1 = Customer(full_name="Иванов Иван Иванович", phone="+79161234567", email="ivanov@mail.ru")
    c2 = Customer(full_name="Смирнова Ольга Павловна", phone="+79269876543", email="smirnova@yandex.ru")
    session.add_all([c1, c2])
    session.commit()

    cards = [
        DiscountCard(customer_id=c1.id, card_number="100200300", discount_percent=10, issue_date=date.today() - timedelta(days=90), valid_until=date.today() + timedelta(days=365)),
        DiscountCard(customer_id=c2.id, card_number="999888777", discount_percent=15, issue_date=date.today() - timedelta(days=400), valid_until=date.today() - timedelta(days=5)),
    ]
    session.add_all(cards)
    session.commit()

    # 7. Тестовая поставка и продажа за сегодня
    sup = Supply(supplier_id=1, store_id=1, supply_date=date.today(), invoice_number="ТН-2026-001", total_amount=19500.00)
    session.add(sup)
    session.commit()
    session.add(SupplyItem(supply_id=sup.id, product_id=1, quantity=30, purchase_price=650.00))

    sale = Sale(date=datetime.now(timezone.utc), user_id=3, store_id=1, customer_id=c1.id, payment_method="Карта", status="Проведено", total=1170.00)
    session.add(sale)
    session.commit()
    session.add(SaleItem(sale_id=sale.id, product_id=1, quantity=2, price_at_sale=650.00, discount_percent=10))
    session.commit()
