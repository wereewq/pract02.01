import glob
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from app.repositories.database import REPORTS_DIR

def _register_cyrillic_font() -> str:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf",
    ] + glob.glob("C:/Windows/Fonts/*.ttf")

    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CyrillicFont", path))
                return "CyrillicFont"
            except Exception:
                continue
    return "Helvetica"

FONT_NAME = _register_cyrillic_font()

def generate_receipt_pdf(sale_id: int, store_name: str, cashier: str, payment_method: str,
                         items: list, subtotal: float, discount_pct: int, total: float) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"receipt_{sale_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = REPORTS_DIR / filename

    doc = SimpleDocTemplate(str(filepath), pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCyr", parent=styles["Heading1"], fontName=FONT_NAME, fontSize=16, alignment=1)
    norm_style = ParagraphStyle("NormCyr", parent=styles["Normal"], fontName=FONT_NAME, fontSize=10, leading=14)

    elements = [
        Paragraph("ООО «КнигоГрад» — Кассовый чек", title_style),
        Spacer(1, 10),
        Paragraph(f"Чек №: {sale_id} | Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", norm_style),
        Paragraph(f"Торговая точка: {store_name}", norm_style),
        Paragraph(f"Кассир: {cashier} | Способ оплаты: {payment_method}", norm_style),
        Spacer(1, 14),
    ]

    table_data = [["№", "Наименование книги", "Кол-во", "Цена, руб.", "Сумма, руб."]]
    for idx, it in enumerate(items, 1):
        table_data.append([str(idx), str(it["title"]), str(it["quantity"]), f"{it['price']:.2f}", f"{it['sum']:.2f}"])

    t = Table(table_data, colWidths=[30, 240, 60, 85, 95])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(f"Сумма без скидки: {subtotal:.2f} руб.", norm_style))
    elements.append(Paragraph(f"Скидка по дисконтной карте: {discount_pct}%", norm_style))
    elements.append(Paragraph(f"ИТОГО К ОПЛАТЕ: {total:.2f} руб.", norm_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Спасибо за покупку! Документ сформирован в ИС «КнигоГрад».", norm_style))

    doc.build(elements)
    return filename

def generate_analytics_pdf(report_title: str, period_str: str, headers: list, rows: list, summary_line: str) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = REPORTS_DIR / filename

    doc = SimpleDocTemplate(str(filepath), pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("RepTitle", parent=styles["Heading1"], fontName=FONT_NAME, fontSize=14, alignment=1)
    norm_style = ParagraphStyle("RepNorm", parent=styles["Normal"], fontName=FONT_NAME, fontSize=10, leading=14)

    elements = [
        Paragraph("ООО «КНИГОГРАД» — АНАЛИТИЧЕСКИЙ ОТЧЁТ", title_style),
        Spacer(1, 6),
        Paragraph(str(report_title), norm_style),
        Paragraph(f"Отчётный период: {period_str} | Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}", norm_style),
        Spacer(1, 14),
    ]

    if not rows:
        elements.append(Paragraph("За выбранный период данные отсутствуют.", norm_style))
    else:
        table_data = [headers] + [[str(cell) for cell in r] for r in rows]
        col_w = 510 // len(headers)
        t = Table(table_data, colWidths=[col_w] * len(headers))
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 16))
    elements.append(Paragraph(str(summary_line), norm_style))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Руководитель филиала ООО «КнигоГрад» ________________ /________________/", norm_style))

    doc.build(elements)
    return filename
