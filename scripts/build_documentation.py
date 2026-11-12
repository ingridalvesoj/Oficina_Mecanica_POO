"""Gera documentação PDF e catálogo UML sem executar a aplicação ou acessar o banco."""

import ast
import re
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PINK = colors.HexColor("#b52d70")
INK = colors.HexColor("#452a38")
PALE = colors.HexColor("#fbe7f0")


def class_catalog():
    paths = [
        "domain/entities.py",
        "domain/enums.py",
        "domain/exceptions.py",
        "application/base.py",
        "application/auth_service.py",
        "application/cadastro_service.py",
        "application/estoque_service.py",
        "application/ordem_service.py",
        "infrastructure/database.py",
        "infrastructure/repositories.py",
    ]
    catalog = {}
    for name in paths:
        tree = ast.parse((ROOT / "src/oficina" / name).read_text(encoding="utf-8"))
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            attributes, methods = [], []
            for node in cls.body:
                if isinstance(node, ast.AnnAssign):
                    attributes.append(f"+ {node.target.id}: {ast.unparse(node.annotation)}")
                elif isinstance(node, ast.Assign) and name.endswith("enums.py"):
                    attributes.append(
                        f"+ {ast.unparse(node.targets[0])}: {ast.unparse(node.value)}"
                    )
                elif isinstance(node, ast.FunctionDef):
                    args = []
                    for arg in node.args.args:
                        if arg.arg in {"self", "cls"}:
                            continue
                        kind = ast.unparse(arg.annotation) if arg.annotation else "Any"
                        args.append(f"{arg.arg}: {kind}")
                    returns = ast.unparse(node.returns) if node.returns else "Any"
                    visibility = "#" if node.name.startswith("_") else "+"
                    prop = (
                        " [property]"
                        if any(ast.unparse(d) == "property" for d in node.decorator_list)
                        else ""
                    )
                    methods.append(f"{visibility} {node.name}({', '.join(args)}): {returns}{prop}")
            if cls.name == "Service":
                attributes.append("+ database: Database")
            if cls.name == "Database":
                attributes.append("+ path: Path")
            if cls.name == "Repository":
                attributes.append("+ connection: sqlite3.Connection")
            catalog[cls.name] = {
                "attributes": attributes,
                "methods": methods,
                "bases": [ast.unparse(base) for base in cls.bases],
                "source": name,
            }
    return catalog


RELATIONS = [
    "Usuario <|-- Administrador",
    "Usuario <|-- Mecanico",
    'Cliente "1" --> "0..*" Veiculo : proprietário',
    'Cliente "1" --> "0..*" OrdemServico : contratante',
    'Veiculo "1" --> "0..*" OrdemServico',
    'Mecanico "0..1" --> "0..*" OrdemServico : responsável',
    'OrdemServico "1" *-- "0..*" ItemPeca',
    'OrdemServico "1" *-- "0..*" ItemServico',
    'ItemPeca "0..*" --> "1" Peca',
    'ItemServico "0..*" --> "1" Servico',
]


def mermaid(catalog, names, relations):
    lines = ["```mermaid", "classDiagram", "direction TB"]
    for name in names:
        lines.append(f"class {name} {{")
        for item in catalog[name]["attributes"] + catalog[name]["methods"]:
            item = item.replace(" | None", "_opcional").replace(" | ", "_ou_")
            item = item.replace("[property]", "").replace("[", "~").replace("]", "~")
            lines.append("    " + item)
        lines.append("}")
    lines.extend(relations)
    lines.append("```")
    return "\n".join(lines)


def write_uml(catalog):
    domain = [name for name, item in catalog.items() if item["source"] == "domain/entities.py"]
    other = [name for name in catalog if name not in domain]
    relations = []
    for name in other:
        for base in catalog[name]["bases"]:
            if base in catalog:
                relations.append(f"{base} <|-- {name}")
    relations += [
        'Service "0..*" --> "1" Database : utiliza',
        "Repository ..> OrdemServico : reconstitui",
        "Repository ..> Usuario : reconstitui perfil concreto",
        "OrdemService ..> Repository",
        "CadastroService ..> Repository",
        "EstoqueService ..> Repository",
        "AuthService ..> Repository",
        "OrdemServico ..> StatusOS",
        "ItemServico ..> StatusServico",
        "Usuario ..> Perfil",
    ]
    text = "# Diagramas de classes e catálogo de assinaturas\n\n"
    text += "Gerado a partir do código. `+` significa público; `#`, uso interno convencional. "
    text += "`Any` indica ausência de anotação explícita, não uma restrição de execução. "
    text += (
        "Propriedades e métodos gerados pelas dataclasses são explicados no documento principal. "
    )
    text += "Construtores gerados recebem os atributos declarados, incluindo valores padrão quando existentes. "
    text += "Os diagramas abreviam valores padrão; as definições Python são a referência exata.\n\n"
    text += "## Domínio\n\n" + mermaid(catalog, domain, RELATIONS)
    text += "\n\n## Aplicação, persistência, enumerações e exceções\n\n" + mermaid(
        catalog, other, relations
    )
    text += "\n\n## Catálogo legível das assinaturas\n\n"
    for name, info in catalog.items():
        text += f"### {name}\n\nOrigem: `src/oficina/{info['source']}`."
        if info["bases"]:
            text += f" Bases: {', '.join(info['bases'])}."
        text += (
            "\n\n```text\n"
            + "\n".join(
                info["attributes"] + info["methods"] or ["Sem membros próprios adicionais."]
            )
            + "\n```\n\n"
        )
    (DOCS / "DIAGRAMA_CLASSES.md").write_text(text, encoding="utf-8")


def domain_drawing(catalog):
    """Vista completa das entidades; linhas passam pelos espaços entre caixas."""
    drawing = Drawing(1080, 700)
    boxes = {}
    positions = {
        "Usuario": (15, 690, 340),
        "Cliente": (440, 690, 220),
        "Veiculo": (800, 690, 250),
        "Administrador": (15, 505, 340),
        "Mecanico": (15, 375, 340),
        "OrdemServico": (440, 440, 360),
        "ItemPeca": (15, 190, 230),
        "Peca": (275, 190, 230),
        "ItemServico": (550, 190, 230),
        "Servico": (810, 190, 230),
    }
    for name, (x, top, width) in positions.items():
        info = catalog[name]
        lines = info["attributes"] + ["---"] + info["methods"]
        wrapped = []
        for line in lines:
            wrapped.extend(textwrap.wrap(line, width=int(width / 5.2)) or [""])
        height = 30 + 12 * len(wrapped)
        boxes[name] = (x, top - height, width, height)
        drawing.add(Rect(x, top - height, width, height, fillColor=colors.white, strokeColor=PINK))
        drawing.add(Rect(x, top - 25, width, 25, fillColor=PALE, strokeColor=PINK))
        drawing.add(
            String(
                x + 9,
                top - 17,
                name + (" [abstrata]" if name == "Usuario" else ""),
                fontName="DocBold",
                fontSize=11,
                fillColor=INK,
            )
        )
        y = top - 39
        for line in wrapped:
            if line == "---":
                drawing.add(Line(x, y + 4, x + width, y + 4, strokeColor=PINK))
            else:
                drawing.add(String(x + 7, y, line, fontName="Doc", fontSize=9, fillColor=INK))
            y -= 12

    def edge(points, label, label_xy, kind="association"):
        for p, q in zip(points, points[1:]):
            drawing.add(Line(*p, *q, strokeColor=INK, strokeWidth=1))
        x, y = points[-1]
        if kind == "inherit":
            drawing.add(
                Polygon(
                    [x, y, x - 5, y - 10, x + 5, y - 10], fillColor=colors.white, strokeColor=INK
                )
            )
        if kind == "composition":
            x, y = points[0]
            drawing.add(
                Polygon(
                    [x, y, x - 4, y - 6, x, y - 12, x + 4, y - 6], fillColor=INK, strokeColor=INK
                )
            )
        drawing.add(
            String(
                *label_xy,
                label,
                fontName="Doc",
                fontSize=6 if label == "0..* / 1" else 9,
                fillColor=INK,
            )
        )

    ux, uy, uw, uh = boxes["Usuario"]
    edge([(170, 505), (170, uy)], "herança", (175, 515), "inherit")
    edge(
        [(15, 350), (3, 350), (3, uy - 15), (65, uy - 15), (65, uy)], "herança", (4, 410), "inherit"
    )
    edge([(660, 640), (800, 640)], "1 proprietário / 0..*", (667, 649))
    edge([(550, boxes["Cliente"][1]), (550, 440)], "1 contratante / 0..*", (557, 470))
    edge(
        [(920, boxes["Veiculo"][1]), (920, 450), (720, 450), (720, 440)],
        "1 veículo / 0..*",
        (812, 462),
    )
    edge([(355, 320), (440, 320)], "0..1 / 0..*", (358, 332))
    bottom = boxes["OrdemServico"][1]
    edge(
        [(490, bottom), (490, 215), (130, 215), (130, 190)],
        "1 OS / 0..* itens",
        (200, 222),
        "composition",
    )
    edge([(720, bottom), (720, 215), (660, 215), (660, 190)], "1 / 0..*", (725, 222), "composition")
    edge([(245, 130), (275, 130)], "0..* / 1", (248, 143))
    edge([(780, 130), (810, 130)], "0..* / 1", (781, 143))
    drawing.scale(0.93, 0.93)
    drawing.width *= 0.93
    drawing.height *= 0.93
    return drawing


def build_pdf(catalog):
    styles = getSampleStyleSheet()
    for key in ["Normal", "BodyText", "Heading1", "Heading2", "Heading3", "Title"]:
        styles[key].fontName = "DocBold" if key.startswith("Heading") or key == "Title" else "Doc"
        styles[key].textColor = INK
    styles["BodyText"].fontSize = 10
    styles["BodyText"].leading = 14
    styles["BodyText"].spaceAfter = 7
    styles["Heading1"].fontSize = 18
    styles["Heading1"].leading = 23
    styles["Heading1"].spaceBefore = 14
    styles["Heading2"].fontSize = 13
    styles["Heading2"].leading = 17
    styles.add(
        ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=8, leading=11, spaceAfter=0)
    )
    styles.add(
        ParagraphStyle(
            "CodeLine",
            parent=styles["BodyText"],
            fontSize=8,
            leading=11,
            leftIndent=9,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            "Cover", parent=styles["Title"], fontSize=29, leading=34, alignment=TA_CENTER
        )
    )

    def rich(text):
        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"`([^`]+)`", r"<font color='#84234e'>\1</font>", text)
        return text

    def para(text, style="BodyText"):
        return Paragraph(rich(text), styles[style])

    def parse(text):
        result, lines, i = [], text.splitlines(), 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("```"):
                lang = line[3:]
                i += 1
                block = []
                while i < len(lines) and not lines[i].startswith("```"):
                    block.append(lines[i])
                    i += 1
                if lang == "mermaid":
                    if "stateDiagram" in "\n".join(block):
                        result.append(
                            para(
                                "Fluxo: Em orçamento → Aguardando aprovação → Aprovada → Em execução → Concluída. Retornos e cancelamentos: conforme as transições descritas acima."
                            )
                        )
                else:
                    for code in block:
                        for part in textwrap.wrap(code, width=106, subsequent_indent="    ") or [
                            ""
                        ]:
                            result.append(para(part, "CodeLine"))
                    result.append(Spacer(1, 6))
            elif line.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                        rows.append([para(c, "Cell") for c in cells])
                    i += 1
                i -= 1
                count = len(rows[0])
                widths = {2: [95, 404], 3: [115, 180, 204], 4: [65, 120, 155, 159]}.get(count)
                table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT", splitInRow=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), PALE),
                            (
                                "ROWBACKGROUNDS",
                                (0, 1),
                                (-1, -1),
                                [colors.white, colors.HexColor("#fff8fc")],
                            ),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEBELOW", (0, 0), (-1, 0), 1, PINK),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                            ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ]
                    )
                )
                result.extend([table, Spacer(1, 10)])
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                result.append(para(line.lstrip("# "), f"Heading{min(level, 3)}"))
            else:
                result.append(para(line))
            i += 1
        return result

    def footer(canvas, doc):
        width, height = canvas._pagesize
        canvas.saveState()
        canvas.setFont("Doc", 8)
        canvas.setFillColor(INK)
        canvas.drawString(
            17 * mm, 12 * mm, "Oficina Mecânica | Documentação do sistema | 09/11/2026"
        )
        canvas.drawRightString(width - 17 * mm, 12 * mm, str(doc.page))
        canvas.setStrokeColor(PINK)
        canvas.line(17 * mm, 17 * mm, width - 17 * mm, 17 * mm)
        canvas.restoreState()

    portrait = Frame(
        17 * mm,
        22 * mm,
        A4[0] - 34 * mm,
        A4[1] - 42 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    wide_size = landscape(A3)
    wide = Frame(
        17 * mm,
        22 * mm,
        wide_size[0] - 34 * mm,
        wide_size[1] - 42 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = BaseDocTemplate(
        str(DOCS / "DOCUMENTACAO.pdf"),
        pagesize=A4,
        title="Oficina Mecânica - Documentação do sistema",
        author="Ingrid Alves Oliveira de Jesus",
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="portrait", frames=[portrait], onPage=footer, pagesize=A4),
            PageTemplate(id="wide", frames=[wide], onPage=footer, pagesize=wide_size),
        ]
    )
    logo = Image(
        str(ROOT / "src/oficina/assets/logo.png"),
        width=90 * mm,
        height=60 * mm,
        kind="proportional",
    )
    story = [
        Spacer(1, 24 * mm),
        logo,
        Spacer(1, 14 * mm),
        para("Oficina Mecânica", "Cover"),
        para("Gestão de Ordem de Serviço Automotiva", "Title"),
        Spacer(1, 15 * mm),
        para("Programação Orientada a Objetos - BRIPROO 2026/2"),
        para("Ingrid Alves Oliveira de Jesus | BI-3018521"),
        para("Atividades 1 a 4 e implementação atual"),
        para("Revisão de 09/11/2026"),
        PageBreak(),
    ]
    story += parse((DOCS / "DOCUMENTACAO.md").read_text(encoding="utf-8"))
    story += [
        NextPageTemplate("wide"),
        PageBreak(),
        para("Anexo A - Diagrama completo do domínio", "Heading1"),
        domain_drawing(catalog),
    ]
    story += [
        PageBreak(),
        para("Anexo A - Dependências e herança de suporte", "Heading1"),
        support_drawing(),
    ]
    story += [NextPageTemplate("portrait"), PageBreak()]
    uml = (DOCS / "DIAGRAMA_CLASSES.md").read_text(encoding="utf-8")
    story += parse(
        "# Anexo B - Assinaturas das classes\n\nAny indica ausência de anotação no código; + indica público e # uso interno convencional.\n\n"
        + uml.split("## Catálogo legível das assinaturas")[1]
    )
    doc.build(story)


def support_drawing():
    drawing = Drawing(1080, 650)

    def box(x, y, width, title, lines):
        height = 40 + len(lines) * 18
        drawing.add(Rect(x, y - height, width, height, fillColor=colors.white, strokeColor=PINK))
        drawing.add(Rect(x, y - 28, width, 28, fillColor=PALE, strokeColor=PINK))
        drawing.add(String(x + 10, y - 19, title, fontName="DocBold", fontSize=12, fillColor=INK))
        for i, line in enumerate(lines):
            drawing.add(
                String(x + 10, y - 46 - i * 18, line, fontName="Doc", fontSize=10, fillColor=INK)
            )

    box(
        350,
        630,
        380,
        "Service",
        [
            "+ database: Database",
            "+ actor(connection, user_id, admin=False): Usuario",
            "+ active(row, label): None",
        ],
    )
    for x, title, lines in [
        (0, "AuthService", ["bootstrap, has_users, login, current"]),
        (275, "CadastroService", ["list, get, save, set_active, delete"]),
        (550, "EstoqueService", ["enter, withdraw, move, balances, history"]),
        (825, "OrdemService", ["OS, itens, estados, serviços, PDF, finanças"]),
    ]:
        box(x, 410, 255, title, lines + ["Herda database e operações de Service."])
        drawing.add(Line(x + 127, 410, x + 127, 460, strokeColor=INK))
        drawing.add(Line(x + 127, 460, 540, 460, strokeColor=INK))
    drawing.add(Line(540, 460, 540, 530, strokeColor=INK))
    drawing.add(Polygon([540, 536, 534, 525, 546, 525], fillColor=colors.white, strokeColor=INK))
    drawing.add(
        String(
            555, 480, "generalização / especialização", fontName="Doc", fontSize=10, fillColor=INK
        )
    )
    box(
        20,
        255,
        470,
        "Database",
        [
            "+ path: Path",
            "+ connect(): sqlite3.Connection",
            "+ transaction(write=False): gerenciador de contexto",
            "+ migrate(): None",
        ],
    )
    box(
        590,
        255,
        470,
        "Repository",
        [
            "+ connection: sqlite3.Connection",
            "+ get, user, entity, order, available",
            "Reconstrói entidades e calcula estoque disponível.",
            "Assinaturas completas no Anexo B e no Markdown UML.",
        ],
    )
    drawing.add(Line(490, 185, 590, 185, strokeColor=INK))
    drawing.add(String(495, 198, "conexão", fontName="Doc", fontSize=10, fillColor=INK))
    drawing.add(
        String(
            20,
            60,
            "Serviços usam Database e Repository; estes não dependem das telas Streamlit.",
            fontName="Doc",
            fontSize=12,
            fillColor=INK,
        )
    )
    drawing.add(
        String(
            20,
            35,
            "Esta vista sintetiza as dependências. O catálogo anexo detalha todas as operações, enums e exceções.",
            fontName="Doc",
            fontSize=11,
            fillColor=INK,
        )
    )
    return drawing


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    fonts = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("Doc", str(fonts / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("DocBold", str(fonts / "arialbd.ttf")))
    pdfmetrics.registerFontFamily(
        "Doc", normal="Doc", bold="DocBold", italic="Doc", boldItalic="DocBold"
    )
    classes = class_catalog()
    write_uml(classes)
    build_pdf(classes)
    print("Documentação e catálogo UML gerados em docs/.")
