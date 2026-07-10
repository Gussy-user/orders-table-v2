import os
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _register_fonts():
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("RuFont", path))
                return "RuFont"
            except Exception:
                continue
    return "Helvetica"


_FONT = None


def _get_font():
    global _FONT
    if _FONT is None:
        _FONT = _register_fonts()
    return _FONT


def generate_invoice_pdf(client, order=None, employee="", shop_address=""):
    if order is None:
        active = [o for o in client.orders if not o.archived]
        order = active[0] if active else None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )

    font = _get_font()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "RuTitle", parent=styles["Title"],
        fontName=font, fontSize=16, spaceAfter=6,
    )
    normal_style = ParagraphStyle(
        "RuNormal", parent=styles["Normal"],
        fontName=font, fontSize=10, leading=14,
    )
    bold_style = ParagraphStyle(
        "RuBold", parent=styles["Normal"],
        fontName=font, fontSize=10, leading=14,
    )
    small_style = ParagraphStyle(
        "RuSmall", parent=styles["Normal"],
        fontName=font, fontSize=8, leading=11, textColor=colors.grey,
    )

    elements = []

    # === Заголовок ===
    elements.append(Paragraph("РАСЧЁТНЫЙ ЛИСТ", title_style))
    elements.append(Spacer(1, 4 * mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0d6efd")))
    elements.append(Spacer(1, 4 * mm))

    # === Информация ===
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    order_status = order.status.name if order and order.status else "—"

    info_data = [
        [Paragraph("<b>Клиент:</b>", normal_style), Paragraph(client.name, normal_style)],
        [Paragraph("<b>Телефон:</b>", normal_style), Paragraph(client.phone, normal_style)],
        [Paragraph("<b>Заказ:</b>", normal_style), Paragraph(order.order_number if order else "—", normal_style)],
        [Paragraph("<b>Статус заказа:</b>", normal_style), Paragraph(order_status, normal_style)],
        [Paragraph("<b>Дата формирования:</b>", normal_style), Paragraph(now_str, normal_style)],
    ]

    if employee:
        info_data.append([Paragraph("<b>Сотрудник:</b>", normal_style), Paragraph(employee, normal_style)])
    if shop_address:
        info_data.append([Paragraph("<b>Магазин:</b>", normal_style), Paragraph(shop_address, normal_style)])

    info_table = Table(info_data, colWidths=[45 * mm, 120 * mm])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # === Автомобили ===
    if client.cars:
        elements.append(Paragraph("<b>Автомобили:</b>", bold_style))
        elements.append(Spacer(1, 2 * mm))
        cars_data = [["Марка", "Модель", "VIN", "Год"]]
        for car in client.cars:
            cars_data.append([
                car.make, car.model, car.vin,
                str(car.year) if car.year else "—",
            ])
        cars_table = Table(cars_data, colWidths=[40 * mm, 40 * mm, 60 * mm, 25 * mm])
        cars_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(cars_table)
        elements.append(Spacer(1, 6 * mm))

    # === Позиции заказа ===
    if order:
        elements.append(Paragraph("<b>Позиции заказа:</b>", bold_style))
        elements.append(Spacer(1, 2 * mm))

        order_total = order.total_price
        header = ["#", "Деталь", "Артикул", "Кол-во", "Цена, руб.", "Итого, руб."]
        rows = [header]
        for idx, item in enumerate(order.items, 1):
            rows.append([
                str(idx),
                item.part_name,
                item.article or "—",
                str(item.quantity),
                f"{item.price:.2f}",
                f"{item.total:.2f}",
            ])
        rows.append(["", "", "", "", "ИТОГО:", f"{order_total:.2f} руб."])

        t = Table(rows, colWidths=[10 * mm, 50 * mm, 30 * mm, 18 * mm, 28 * mm, 28 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f0f0")),
            ("FONTNAME", (0, -1), (-1, -1), font),
            ("FONTSIZE", (0, -1), (-1, -1), 10),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("Заказов пока нет.", normal_style))

    # === Подписи (одна строка, жирный, с линиями) ===
    elements.append(Spacer(1, 15 * mm))
    sig_style = ParagraphStyle(
        "RuSig", parent=styles["Normal"],
        fontName=font, fontSize=10, leading=14,
    )
    sig_line_style = ParagraphStyle(
        "RuSigLine", parent=styles["Normal"],
        fontName=font, fontSize=10, leading=14,
    )
    sig_data = [[
        Paragraph("<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> (ФИО) &nbsp;&nbsp; <b>Подпись:</b> __________", sig_style),
        Paragraph("<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> (ФИО) &nbsp;&nbsp; <b>Подпись:</b> __________", sig_style),
    ]]
    sig_table = Table(sig_data, colWidths=[80 * mm, 80 * mm])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(sig_table)

    # === Подвал ===
    elements.append(Spacer(1, 10 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Документ сформирован {now_str}",
        small_style,
    ))

    doc.build(elements)
    return buf.getvalue()
