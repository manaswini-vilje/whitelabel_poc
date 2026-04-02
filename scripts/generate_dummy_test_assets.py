#!/usr/bin/env python3
"""Generate synthetic PDF and expected JSON test assets for the white-label app."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "samples"
PDF_PATH = SAMPLES_DIR / "dummy_kitchen_supplier_invoice.pdf"
EXPECTED_JSON_PATH = SAMPLES_DIR / "dummy_kitchen_supplier_expected_output.json"

DOCUMENT_NUMBER = "FA/90017/2026/DUMMY"
ISSUE_DATE = "15-03-2026"

SUPPLIER = {
    "name": "Aurora Living Wholesale Sp. z o.o.",
    "address": "18 Harbor Trade Street, 80-221 Gdansk",
    "phone": "+48 58 555 2100",
}

BUYER = {
    "name": "Northwind Home Retail AB",
    "address": "44 Market Square, 111 29 Stockholm, Sweden",
}

PRODUCTS = [
    ("1", "Stoneware Dinner Plate 27cm", "KDN000141", "Sand Beige", "AL-2026-0315-01", "5901001000011", 4, 3.60, 4.00),
    ("2", "Stoneware Pasta Bowl 22cm", "KDN000142", "Sand Beige", "AL-2026-0315-02", "5901001000012", 4, 3.20, 3.55),
    ("3", "Double Wall Glass Mug Set", "KDN000215", "Clear", "AL-2026-0315-03", "5901001000013", 2, 1.10, 1.30),
    ("4", "Acacia Serving Board Large", "KDN000318", "Natural Oak", "AL-2026-0315-04", "5901001000014", 3, 2.40, 2.70),
    ("5", "Textured Table Runner", "KDN000402", "Olive Stripe", "AL-2026-0315-05", "5901001000015", 5, 1.50, 1.80),
    ("6", "Ceramic Canister 1.2L", "KDN000417", "Matte White", "AL-2026-0315-06", "5901001000016", 2, 1.80, 2.10),
    ("7", "Bamboo Cutlery Tray Expandable", "KDN000509", "Natural", "AL-2026-0315-07", "5901001000017", 3, 2.10, 2.45),
    ("8", "Linen Napkin Set of 4", "KDN000612", "Terracotta", "AL-2026-0315-08", "5901001000018", 6, 1.20, 1.45),
    ("9", "Glass Storage Jar 900ml", "KDN000701", "Clear", "AL-2026-0315-09", "5901001000019", 4, 2.00, 2.30),
    ("10", "Olive Oil Bottle 500ml", "KDN000702", "Smoked Green", "AL-2026-0315-10", "5901001000020", 3, 1.65, 1.90),
    ("11", "Ribbed Water Carafe", "KDN000703", "Clear", "AL-2026-0315-11", "5901001000021", 2, 1.70, 1.95),
    ("12", "Cotton Apron", "KDN000804", "Charcoal", "AL-2026-0315-12", "5901001000022", 5, 1.10, 1.35),
    ("13", "Brass Measuring Spoon Set", "KDN000905", "Brushed Brass", "AL-2026-0315-13", "5901001000023", 4, 0.80, 0.95),
    ("14", "Marble Coaster Set", "KDN000906", "White Stone", "AL-2026-0315-14", "5901001000024", 3, 1.95, 2.20),
    ("15", "Kitchen Towel Set of 3", "KDN001007", "Blue Grid", "AL-2026-0315-15", "5901001000025", 6, 1.50, 1.80),
    ("16", "Ceramic Fruit Bowl", "KDN001108", "Soft Grey", "AL-2026-0315-16", "5901001000026", 2, 1.90, 2.15),
    ("17", "Utensil Crock", "KDN001109", "Soft Grey", "AL-2026-0315-17", "5901001000027", 2, 1.55, 1.80),
    ("18", "Glass Spice Jar Set", "KDN001210", "Clear", "AL-2026-0315-18", "5901001000028", 4, 1.40, 1.65),
]


def build_expected_output() -> dict:
    purchase_order_lines = []
    line_number = 10000

    for _, _, article, _, _, _, quantity, _, _ in PRODUCTS:
        purchase_order_lines.append(
            {
                "line": line_number,
                "itemId": article,
                "dateTime": ISSUE_DATE,
                "quantity": quantity,
                "warehouseId": "NW",
            }
        )
        line_number += 10000

    return {
        "orderType": "PO",
        "orderNr": DOCUMENT_NUMBER,
        "supplier": {
            "id": 0,
            "name": SUPPLIER["name"],
            "address1": SUPPLIER["address"],
            "city": "",
            "country": "SE",
            "mobileNo": SUPPLIER["phone"],
            "email": "",
            "zipCode": "",
        },
        "priority": 3,
        "purchaseOrderLines": purchase_order_lines,
    }


def build_pdf() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1f3b5b"),
        spaceAfter=8,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#2b2b2b"),
    )
    label_style = ParagraphStyle(
        "Label",
        parent=small_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1f3b5b"),
    )

    story = [
        Paragraph("Synthetic Supplier Invoice / Packing List", title_style),
        Paragraph(
            "This sample document is fully dummy data generated for white-label testing.",
            small_style,
        ),
        Spacer(1, 5 * mm),
    ]

    header_data = [
        [
            Paragraph("<b>Document Number</b><br/>" + DOCUMENT_NUMBER, small_style),
            Paragraph("<b>Date of Issue</b><br/>" + ISSUE_DATE, small_style),
            Paragraph("<b>Currency</b><br/>EUR", small_style),
        ],
        [
            Paragraph("<b>Seller</b><br/>" + SUPPLIER["name"] + "<br/>" + SUPPLIER["address"] + "<br/>Phone: " + SUPPLIER["phone"], small_style),
            Paragraph("<b>Payer</b><br/>" + BUYER["name"] + "<br/>" + BUYER["address"], small_style),
            Paragraph("<b>Buyer / Delivery Address</b><br/>" + BUYER["name"] + "<br/>Dock 4 Receiving<br/>Stockholm, Sweden", small_style),
        ],
    ]
    header_table = Table(header_data, colWidths=[60 * mm, 60 * mm, 56 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0f6")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#8aa4c1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d5e3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([header_table, Spacer(1, 6 * mm)])

    story.append(
        Paragraph(
            "<b>Category:</b> Kitchen & Dining Accessories<br/><b>Notes:</b> "
            "All SKUs, quantities, references, and supplier details in this document are synthetic.",
            small_style,
        )
    )
    story.append(Spacer(1, 4 * mm))

    table_headers = [
        Paragraph("<b>Line</b>", label_style),
        Paragraph("<b>Product / Service Name</b>", label_style),
        Paragraph("<b>Article</b>", label_style),
        Paragraph("<b>Fabric / Color</b>", label_style),
        Paragraph("<b>Batch / Order / EAN</b>", label_style),
        Paragraph("<b>Qty</b>", label_style),
        Paragraph("<b>Net Wt</b>", label_style),
        Paragraph("<b>Gross Wt</b>", label_style),
    ]
    table_data = [table_headers]

    total_qty = 0
    total_net = 0.0
    total_gross = 0.0

    for line, name, article, color, order_ref, ean, qty, net_wt, gross_wt in PRODUCTS:
        total_qty += qty
        total_net += net_wt
        total_gross += gross_wt
        combined_ref = f"Batch: {order_ref}, Order: {DOCUMENT_NUMBER}, EAN: {ean}"
        table_data.append(
            [
                line,
                Paragraph(name, small_style),
                article,
                Paragraph(color, small_style),
                Paragraph(combined_ref, small_style),
                qty,
                f"{net_wt:.2f}",
                f"{gross_wt:.2f}",
            ]
        )

    product_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[10 * mm, 48 * mm, 24 * mm, 28 * mm, 48 * mm, 10 * mm, 12 * mm, 14 * mm],
    )
    product_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d6e4f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8c7d9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbfd")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([product_table, Spacer(1, 5 * mm)])

    totals_data = [
        ["Total quantity", str(total_qty)],
        ["Total net weight", f"{total_net:.2f} kg"],
        ["Total gross weight", f"{total_gross:.2f} kg"],
    ]
    totals_table = Table(totals_data, colWidths=[45 * mm, 30 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#8aa4c1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d5e3")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4f8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([totals_table, Spacer(1, 5 * mm)])

    story.append(
        Paragraph(
            "Warehouse preference for expected output: NW<br/>"
            "Expected supplier country in generated PO output: SE",
            small_style,
        )
    )

    doc.build(story)


def write_expected_json() -> None:
    expected_output = build_expected_output()
    with open(EXPECTED_JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(expected_output, handle, indent=4, ensure_ascii=False)


def main() -> int:
    build_pdf()
    write_expected_json()
    print(f"Generated PDF: {PDF_PATH}")
    print(f"Generated expected output JSON: {EXPECTED_JSON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
