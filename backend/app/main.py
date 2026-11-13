import os
import sys
import threading
import webbrowser
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlmodel import Session, select

# Добавляем корень backend в sys.path для корректного запуска из любой директории и PyInstaller
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.repositories.database import init_db, get_session, engine, REPORTS_DIR
from app.models.entities import (
    User, Store, Product, Stock, Supplier, Supply, SupplyItem, Customer, DiscountCard, Sale, SaleItem
)
from app.schemas.dto import (
    LoginRequest, UserCreate, ProductCreate, ProductUpdate, SupplyCreate, SaleCreate, CustomerCreate, ReportRequest
)
from app.services.seed_service import (
    seed_initial_data, verify_password, hash_password, create_token, decode_token
)
from app.services.pdf_service import generate_receipt_pdf, generate_analytics_pdf

app = FastAPI(title="ИС «КнигоГрад: Система учёта продаж и поставок»", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FAILED_ATTEMPTS = {}

def get_current_user(authorization: Optional[str] = Header(None), session: Session = Depends(get_session)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Недействительный или истекший токен")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user

def require_roles(*allowed_roles):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения операции")
        return user
    return checker

@app.on_event("startup")
def on_startup():
    init_db()
    with Session(engine) as session:
        seed_initial_data(session)

# --- АВТОРИЗАЦИЯ И ПОЛЬЗОВАТЕЛИ ---
@app.post("/api/auth/login")
def login(data: LoginRequest, session: Session = Depends(get_session)):
    if FAILED_ATTEMPTS.get(data.login, 0) >= 5:
        raise HTTPException(status_code=429, detail="Учётная запись временно заблокирована после 5 неудачных попыток входа")
    user = session.exec(select(User).where(User.login == data.login)).first()
    if not user or not verify_password(data.password, user.password_hash):
        FAILED_ATTEMPTS[data.login] = FAILED_ATTEMPTS.get(data.login, 0) + 1
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    FAILED_ATTEMPTS[data.login] = 0
    return {
        "access_token": create_token(user),
        "user": {"id": user.id, "login": user.login, "full_name": user.full_name, "role": user.role},
    }

@app.get("/api/users")
def list_users(user: User = Depends(require_roles("Администратор", "Руководитель")), session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return [{"id": u.id, "login": u.login, "full_name": u.full_name, "role": u.role} for u in users]

@app.post("/api/users")
def create_user(data: UserCreate, user: User = Depends(require_roles("Администратор")), session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.login == data.login)).first():
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
    new_u = User(login=data.login, password_hash=hash_password(data.password), full_name=data.full_name, role=data.role)
    session.add(new_u)
    session.commit()
    session.refresh(new_u)
    return {"id": new_u.id, "login": new_u.login, "full_name": new_u.full_name, "role": new_u.role}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, user: User = Depends(require_roles("Администратор")), session: Session = Depends(get_session)):
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target.login == "admin_book":
        raise HTTPException(status_code=400, detail="Нельзя удалить главного администратора")
    session.delete(target)
    session.commit()
    return {"message": "Пользователь удалён"}

# --- МАГАЗИНЫ И ДАШБОРД ---
@app.get("/api/stores")
def get_stores(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(Store)).all()

@app.get("/api/dashboard")
def get_dashboard(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    today = date.today()
    sales = session.exec(select(Sale)).all()
    today_sales = [s for s in sales if s.date.date() == today and s.status == "Проведено"]
    revenue_today = sum(s.total for s in today_sales)

    low_stocks = []
    stocks = session.exec(select(Stock).where(Stock.quantity <= 5)).all()
    for st in stocks:
        prod = session.get(Product, st.product_id)
        store = session.get(Store, st.store_id)
        if prod and store:
            low_stocks.append({
                "product_id": prod.id,
                "title": prod.title,
                "author": prod.author,
                "store_name": store.name,
                "quantity": st.quantity,
            })

    return {
        "sales_count_today": len(today_sales),
        "revenue_today": round(revenue_today, 2),
        "total_products": len(session.exec(select(Product)).all()),
        "total_customers": len(session.exec(select(Customer)).all()),
        "low_stocks": low_stocks[:20],
    }

# --- ТОВАРЫ И ОСТАТКИ ---
@app.get("/api/products")
def list_products(q: Optional[str] = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    stores = session.exec(select(Store)).all()
    if q:
        ql = q.lower().strip()
        products = [p for p in products if ql in p.title.lower() or ql in p.author.lower() or ql in p.isbn.lower() or ql in p.category.lower()]

    result = []
    for p in products:
        store_stocks = {}
        total_qty = 0
        for s in stores:
            st = session.exec(select(Stock).where(Stock.product_id == p.id, Stock.store_id == s.id)).first()
            qty = st.quantity if st else 0
            store_stocks[str(s.id)] = qty
            total_qty += qty
        result.append({
            "id": p.id,
            "title": p.title,
            "author": p.author,
            "category": p.category,
            "price": p.price,
            "isbn": p.isbn,
            "total_stock": total_qty,
            "store_stocks": store_stocks,
        })
    return result

@app.post("/api/products")
def create_product(data: ProductCreate, user: User = Depends(require_roles("Администратор", "Менеджер")), session: Session = Depends(get_session)):
    if session.exec(select(Product).where(Product.isbn == data.isbn)).first():
        raise HTTPException(status_code=400, detail="Товар с таким ISBN уже существует в базе")
    prod = Product(title=data.title, author=data.author, category=data.category, price=data.price, isbn=data.isbn)
    session.add(prod)
    session.commit()
    session.refresh(prod)

    init_map = {1: max(0, data.initial_stock_store_1), 2: max(0, data.initial_stock_store_2), 3: max(0, data.initial_stock_store_3)}
    for sid, qty in init_map.items():
        session.add(Stock(product_id=prod.id, store_id=sid, quantity=qty))
    session.commit()
    return {"message": "Товар успешно добавлен", "id": prod.id}

@app.put("/api/products/{product_id}")
def update_product(product_id: int, data: ProductUpdate, user: User = Depends(require_roles("Администратор", "Менеджер")), session: Session = Depends(get_session)):
    prod = session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if data.price <= 0:
        raise HTTPException(status_code=400, detail="Цена должна быть положительной")
    prod.title = data.title
    prod.author = data.author
    prod.category = data.category
    prod.price = round(data.price, 2)
    prod.isbn = data.isbn
    session.add(prod)
    session.commit()
    return {"message": "Данные товара обновлены"}

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, user: User = Depends(require_roles("Администратор")), session: Session = Depends(get_session)):
    prod = session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Товар не найден")
    has_sales = session.exec(select(SaleItem).where(SaleItem.product_id == product_id)).first()
    if has_sales:
        raise HTTPException(status_code=400, detail="Невозможно удалить товар, участвующий в оформленных продажах")
    stocks = session.exec(select(Stock).where(Stock.product_id == product_id)).all()
    for st in stocks:
        session.delete(st)
    session.delete(prod)
    session.commit()
    return {"message": "Товар удалён"}

# --- ПОСТАВЩИКИ И ПОСТАВКИ ---
@app.get("/api/suppliers")
def list_suppliers(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(Supplier)).all()

@app.get("/api/supplies")
def list_supplies(q: Optional[str] = None, user: User = Depends(require_roles("Администратор", "Менеджер", "Руководитель")), session: Session = Depends(get_session)):
    supplies = session.exec(select(Supply).order_by(Supply.id.desc())).all()
    res = []
    for sp in supplies:
        if q and q.lower() not in sp.invoice_number.lower():
            continue
        sup = session.get(Supplier, sp.supplier_id)
        store = session.get(Store, sp.store_id)
        items = session.exec(select(SupplyItem).where(SupplyItem.supply_id == sp.id)).all()
        res.append({
            "id": sp.id,
            "supply_date": sp.supply_date.strftime("%d.%m.%Y"),
            "supplier_name": sup.name if sup else "—",
            "store_name": store.name if store else "—",
            "invoice_number": sp.invoice_number,
            "items_count": len(items),
            "total_amount": sp.total_amount,
        })
    return res

@app.post("/api/supplies")
def create_supply(data: SupplyCreate, user: User = Depends(require_roles("Администратор", "Менеджер")), session: Session = Depends(get_session)):
    if not data.items:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одну позицию в поставку")
    total = 0.0
    for it in data.items:
        if it.quantity <= 0 or it.purchase_price <= 0:
            raise HTTPException(status_code=400, detail="Количество и закупочная цена должны быть больше 0")
        total += it.quantity * it.purchase_price

    supply = Supply(
        supplier_id=data.supplier_id,
        store_id=data.store_id,
        supply_date=data.supply_date,
        invoice_number=data.invoice_number,
        total_amount=round(total, 2),
    )
    session.add(supply)
    session.commit()
    session.refresh(supply)

    for it in data.items:
        session.add(SupplyItem(supply_id=supply.id, product_id=it.product_id, quantity=it.quantity, purchase_price=it.purchase_price))
        st = session.exec(select(Stock).where(Stock.product_id == it.product_id, Stock.store_id == data.store_id)).first()
        if st:
            st.quantity += it.quantity
            session.add(st)
        else:
            session.add(Stock(product_id=it.product_id, store_id=data.store_id, quantity=it.quantity))
    session.commit()
    return {"message": "Поставка зарегистрирована, остатки по магазину обновлены", "id": supply.id}

# --- КЛИЕНТЫ И ДИСКОНТНЫЕ КАРТЫ ---
@app.get("/api/customers")
def list_customers(q: Optional[str] = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    customers = session.exec(select(Customer)).all()
    res = []
    for c in customers:
        if q and q.lower() not in c.full_name.lower() and q.lower() not in c.phone.lower():
            continue
        card = session.exec(select(DiscountCard).where(DiscountCard.customer_id == c.id)).first()
        sales = session.exec(select(Sale).where(Sale.customer_id == c.id, Sale.status == "Проведено")).all()
        res.append({
            "id": c.id,
            "full_name": c.full_name,
            "phone": c.phone,
            "email": c.email,
            "card_number": card.card_number if card else "Нет карты",
            "discount_percent": card.discount_percent if card else 0,
            "valid_until": card.valid_until.strftime("%d.%m.%Y") if (card and card.valid_until) else "Бессрочно",
            "purchases_count": len(sales),
            "purchases_sum": round(sum(s.total for s in sales), 2),
        })
    return res

@app.post("/api/customers")
def create_customer(data: CustomerCreate, user: User = Depends(require_roles("Администратор", "Менеджер", "Кассир")), session: Session = Depends(get_session)):
    if session.exec(select(Customer).where(Customer.email == data.email)).first():
        raise HTTPException(status_code=400, detail="Клиент с таким Email уже существует")
    cust = Customer(full_name=data.full_name, phone=data.phone, email=data.email)
    session.add(cust)
    session.commit()
    session.refresh(cust)

    if data.card_number:
        if session.exec(select(DiscountCard).where(DiscountCard.card_number == data.card_number)).first():
            raise HTTPException(status_code=400, detail="Дисконтная карта с таким номером уже зарегистрирована")
        session.add(DiscountCard(
            customer_id=cust.id,
            card_number=data.card_number,
            discount_percent=data.discount_percent,
            valid_until=data.valid_until,
        ))
        session.commit()
    return {"message": "Клиент сохранён", "id": cust.id}

@app.delete("/api/customers/{customer_id}")
def delete_customer(customer_id: int, user: User = Depends(require_roles("Администратор")), session: Session = Depends(get_session)):
    cust = session.get(Customer, customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    if session.exec(select(Sale).where(Sale.customer_id == customer_id)).first():
        raise HTTPException(status_code=400, detail="Невозможно удалить клиента с историей покупок")
    cards = session.exec(select(DiscountCard).where(DiscountCard.customer_id == customer_id)).all()
    for cd in cards:
        session.delete(cd)
    session.delete(cust)
    session.commit()
    return {"message": "Клиент удалён"}

@app.get("/api/cards/{card_number}")
def check_card(card_number: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    card = session.exec(select(DiscountCard).where(DiscountCard.card_number == card_number.strip())).first()
    if not card:
        raise HTTPException(status_code=404, detail="Дисконтная карта не найдена")
    if card.valid_until and card.valid_until < date.today():
        raise HTTPException(status_code=400, detail="Срок действия дисконтной карты истёк")
    cust = session.get(Customer, card.customer_id)
    return {
        "card_number": card.card_number,
        "discount_percent": card.discount_percent,
        "customer_name": cust.full_name if cust else "Клиент",
    }

# --- ПРОДАЖИ И ЧЕКИ ---
@app.get("/api/sales")
def list_sales(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    sales = session.exec(select(Sale).order_by(Sale.id.desc())).all()
    res = []
    for s in sales:
        store = session.get(Store, s.store_id)
        cashier = session.get(User, s.user_id)
        cust = session.get(Customer, s.customer_id) if s.customer_id else None
        res.append({
            "id": s.id,
            "date": s.date.strftime("%d.%m.%Y %H:%M"),
            "store_name": store.name if store else "—",
            "cashier": cashier.full_name if cashier else "—",
            "customer": cust.full_name if cust else "Розничный покупатель",
            "payment_method": s.payment_method,
            "status": s.status,
            "total": s.total,
        })
    return res

@app.post("/api/sales")
def create_sale(data: SaleCreate, user: User = Depends(require_roles("Администратор", "Менеджер", "Кассир")), session: Session = Depends(get_session)):
    if not data.items:
        raise HTTPException(status_code=400, detail="Корзина пуста. Добавьте товары для оформления продажи")

    discount_pct = 0
    customer_id = None
    if data.card_number and data.card_number.strip():
        card = session.exec(select(DiscountCard).where(DiscountCard.card_number == data.card_number.strip())).first()
        if not card:
            raise HTTPException(status_code=400, detail="Указанная дисконтная карта не найдена")
        if card.valid_until and card.valid_until < date.today():
            raise HTTPException(status_code=400, detail="Срок действия дисконтной карты истёк")
        discount_pct = card.discount_percent
        customer_id = card.customer_id

    prepared_items = []
    subtotal = 0.0
    for it in data.items:
        if it.quantity <= 0:
            raise HTTPException(status_code=400, detail="Количество товара должно быть больше 0")
        prod = session.get(Product, it.product_id)
        if not prod:
            raise HTTPException(status_code=404, detail="Товар не найден")
        st = session.exec(select(Stock).where(Stock.product_id == prod.id, Stock.store_id == data.store_id)).first()
        avail = st.quantity if st else 0
        if avail < it.quantity:
            raise HTTPException(status_code=400, detail=f"Недостаточно товара «{prod.title}» на складе (доступно: {avail} шт.)")
        line_sum = round(prod.price * it.quantity, 2)
        subtotal += line_sum
        prepared_items.append((prod, st, it.quantity, line_sum))

    total = round(subtotal * (100 - discount_pct) / 100.0, 2)
    sale = Sale(
        date=datetime.now(timezone.utc),
        user_id=user.id,
        store_id=data.store_id,
        customer_id=customer_id,
        payment_method=data.payment_method,
        status="Проведено",
        total=total,
    )
    session.add(sale)
    session.commit()
    session.refresh(sale)

    receipt_rows = []
    for prod, st, qty, line_sum in prepared_items:
        st.quantity -= qty
        session.add(st)
        session.add(SaleItem(sale_id=sale.id, product_id=prod.id, quantity=qty, price_at_sale=prod.price, discount_percent=discount_pct))
        receipt_rows.append({"title": prod.title, "quantity": qty, "price": prod.price, "sum": line_sum})
    session.commit()

    store = session.get(Store, data.store_id)
    pdf_file = generate_receipt_pdf(
        sale_id=sale.id,
        store_name=store.name if store else "Магазин",
        cashier=user.full_name,
        payment_method=data.payment_method,
        items=receipt_rows,
        subtotal=subtotal,
        discount_pct=discount_pct,
        total=total,
    )
    return {
        "message": "Продажа зарегистрирована",
        "sale_id": sale.id,
        "total": total,
        "pdf_url": f"/api/reports/file/{pdf_file}",
    }

# --- ОТЧЁТНОСТЬ В PDF ---
@app.get("/api/reports")
def list_reports(user: User = Depends(get_current_user)):
    files_list = sorted(REPORTS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "filename": f.name,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M"),
            "size_kb": max(1, round(f.stat().st_size / 1024, 1)),
            "url": f"/api/reports/file/{f.name}",
        }
        for f in files_list
    ]

@app.post("/api/reports/generate")
def generate_report(data: ReportRequest, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        if data.date_from > data.date_to:
            raise HTTPException(status_code=400, detail="???? ?????? ??????? ?? ????? ???? ????? ???? ?????????")

        period_str = f"{data.date_from.strftime('%d.%m.%Y')} ? {data.date_to.strftime('%d.%m.%Y')}"

        if data.report_type == "sales_period":
            sales = session.exec(select(Sale)).all()
            filtered = [s for s in sales if data.date_from <= s.date.date() <= data.date_to and s.status == "?????????"]
            if data.store_id:
                filtered = [s for s in filtered if s.store_id == data.store_id]
            headers = ["??? ?", "???? ? ?????", "???????", "??????", "?????, ???."]
            rows = []
            for s in filtered:
                st = session.get(Store, s.store_id)
                rows.append([s.id, s.date.strftime("%d.%m.%Y %H:%M"), st.name if st else "?", s.payment_method, f"{s.total:.2f}"])
            total_sum = sum(s.total for s in filtered)
            fname = generate_analytics_pdf(
                "????? ???????? ?? ???????",
                period_str,
                headers,
                rows,
                f"????? ?????: {len(filtered)} | ????? ??????? ?? ??????: {total_sum:.2f} ???.",
            )
        elif data.report_type == "low_stock":
            stocks = session.exec(select(Stock).where(Stock.quantity <= data.stock_threshold)).all()
            headers = ["ID", "?????", "?????", "???????", "???????, ??."]
            rows = []
            for st in stocks:
                if data.store_id and st.store_id != data.store_id:
                    continue
                p = session.get(Product, st.product_id)
                s = session.get(Store, st.store_id)
                if p and s:
                    rows.append([p.id, p.title, p.author, s.name, st.quantity])
            fname = generate_analytics_pdf(
                f"????? ???????? ? ??????? ??????? (????? <= {data.stock_threshold} ??.)?",
                period_str,
                headers,
                rows,
                f"???????? ???????, ????????? ??????????: {len(rows)}",
            )
        else:
            customers = session.exec(select(Customer)).all()
            headers = ["??? ???????", "???????", "???-?? ???????", "????? ?????, ???."]
            rows = []
            for c in customers:
                csales = [s for s in session.exec(select(Sale).where(Sale.customer_id == c.id, Sale.status == "?????????")).all()
                          if data.date_from <= s.date.date() <= data.date_to]
                rows.append([c.full_name, c.phone, len(csales), f"{sum(x.total for x in csales):.2f}"])
            fname = generate_analytics_pdf(
                "????? ??????????? ?????????",
                period_str,
                headers,
                rows,
                f"????? ???????? ? ????: {len(customers)}",
            )

        return {"message": "PDF-????? ??????? ???????????", "filename": fname, "url": f"/api/reports/file/{fname}"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"?????? ????????? PDF: {type(e).__name__}: {e}")

@app.get("/api/reports/file/{filename}")
def download_report_file(filename: str):
    fpath = REPORTS_DIR / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Файл отчёта не найден")
    return FileResponse(path=str(fpath), media_type="application/pdf", filename=filename)

@app.delete("/api/reports/file/{filename}")
def delete_report_file(filename: str, user: User = Depends(require_roles("Администратор", "Руководитель"))):
    fpath = REPORTS_DIR / filename
    if fpath.exists():
        fpath.unlink()
    return {"message": "Файл отчёта удалён"}

# --- КЛИЕНТСКИЙ ВЕБ-ИНТЕРФЕЙС (HTML/CSS/JS ПО МАКЕТУ МП) ---
def _resolve_frontend_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend" / "index.html"
    return BACKEND_ROOT.parent / "frontend" / "index.html"

@app.get("/", response_class=HTMLResponse)
def serve_spa():
    html_file = _resolve_frontend_path()
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))

def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
