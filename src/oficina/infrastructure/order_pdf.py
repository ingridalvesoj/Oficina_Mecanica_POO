"""Exportação em memória, com quebra de páginas e cabeçalhos repetidos."""

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def money(value: int) -> str:
    whole, fraction = divmod(value, 100)
    return f"R$ {whole:,}".replace(",", ".") + f",{fraction:02d}"


def local_date(value: str | None) -> str:
    if not value:
        return "Não registrado"
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(ZoneInfo("America/Sao_Paulo"))
        .strftime("%d/%m/%Y %H:%M")
    )


def render_order_pdf(detail: dict) -> bytes:
    order, vehicle, meta = detail["order"], detail["veiculo"], detail["metadata"]
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=20 * mm,
        title=f"Ordem de serviço {order.id}",
        author="Oficina",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "OficinaTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=colors.HexColor("#84234e"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            "OficinaBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            spaceAfter=7,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "OficinaCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "OficinaTotal",
            parent=styles["Heading2"],
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#84234e"),
            spaceBefore=12,
            spaceAfter=14,
        )
    )

    def paragraph(value, style="OficinaBody"):
        safe = escape(str(value)).replace("\n", "<br/>")
        return Paragraph(safe, styles[style])

    story = [paragraph("OFICINA · ORDEM DE SERVIÇO", "OficinaTitle")]
    story.extend(
        [
            paragraph(f"OS {order.id} | Situação: {order.status}"),
            paragraph(f"Cliente: {detail['cliente']}"),
            paragraph(
                f"Veículo: {vehicle['marca']} {vehicle['modelo']} | Ano: {vehicle['ano']} | Placa: {vehicle['placa']}"
            ),
            paragraph(f"Abertura: {local_date(meta['data_abertura'])}"),
            paragraph("Problema relatado", "Heading2"),
            paragraph(order.problema),
            Spacer(1, 5 * mm),
            paragraph("Peças e serviços", "Heading2"),
        ]
    )
    rows = [
        [paragraph(x, "OficinaCell") for x in ["Tipo", "Descrição", "Qtd.", "Unitário", "Subtotal"]]
    ]
    for item in order.pecas:
        rows.append(
            [
                paragraph(x, "OficinaCell")
                for x in [
                    "Peça",
                    item.descricao,
                    item.quantidade,
                    money(item.valor_centavos),
                    money(item.subtotal),
                ]
            ]
        )
    for item in order.servicos:
        rows.append(
            [
                paragraph(x, "OficinaCell")
                for x in [
                    "Serviço",
                    f"{item.descricao}\nSituação: {item.status}",
                    1,
                    money(item.valor_centavos),
                    money(item.valor_centavos),
                ]
            ]
        )
    if len(rows) == 1:
        story.append(paragraph("Nenhum item adicionado à ordem."))
    else:
        table = Table(
            rows,
            colWidths=[18 * mm, 80 * mm, 12 * mm, 32 * mm, 32 * mm],
            repeatRows=1,
            hAlign="LEFT",
            splitInRow=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4cede")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#fff5f9")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#b52d70")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#eedbe3")),
                ]
            )
        )
        story.append(table)
    story.append(paragraph(f"Total da OS: {money(order.total)}", "OficinaTotal"))
    if order.status == "Cancelada":
        story.append(
            paragraph("Ordem cancelada. O total representa o orçamento histórico, sem cobrança.")
        )
    invoice, payment = detail.get("fatura"), detail.get("pagamento")
    if invoice:
        story.append(
            paragraph(
                f"Faturamento: {money(invoice['valor_centavos'])} em {local_date(invoice['data'])}"
            )
        )
    if payment:
        story.append(
            paragraph(
                f"Pagamento: {payment['forma']} | {money(payment['valor_centavos'])} | {local_date(payment['data'])}"
            )
        )
    if meta.get("data_conclusao"):
        story.append(paragraph(f"Conclusão: {local_date(meta['data_conclusao'])}"))
    if meta.get("data_entrega"):
        story.append(paragraph(f"Entrega: {local_date(meta['data_entrega'])}"))
    story.append(Spacer(1, 5 * mm))
    story.append(paragraph("Documento de acompanhamento do atendimento. Não é documento fiscal."))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#edc9d9"))
        canvas.line(18 * mm, 16 * mm, 192 * mm, 16 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#75485c"))
        canvas.drawString(18 * mm, 11 * mm, f"Oficina | OS {order.id}")
        canvas.drawRightString(192 * mm, 11 * mm, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
