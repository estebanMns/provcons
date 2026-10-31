import asyncio
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.core.exceptions import ValidationError
from app.infrastructure.documents import extract_json_from_upload, spreadsheet_to_text


def _xlsx(sheets: dict[str, list[list]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets.items():
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class FakeAI:
    def __init__(self):
        self.calls = []

    async def generate_json(self, prompt, system_instruction, **kwargs):
        self.calls.append(("texto", prompt))
        return {"items": []}

    async def generate_json_from_file(self, file_bytes, mime_type, system_instruction, **kwargs):
        self.calls.append(("archivo", mime_type))
        return {"items": []}


def test_excel_a_texto_con_todas_las_hojas_y_sin_filas_vacias():
    data = _xlsx({
        "Cementos": [["Producto", "Unidad", "Precio", "Stock"], ["Cemento gris 50kg", "bulto", 25000.0, 150], [None, None, None, None]],
        "Aceros": [["Varilla 3/8 x 6m", "und", 18500, 300]],
    })
    text = spreadsheet_to_text(data)
    assert text.splitlines() == [
        "## Hoja: Cementos",
        "Producto | Unidad | Precio | Stock",
        "Cemento gris 50kg | bulto | 25000 | 150",
        "## Hoja: Aceros",
        "Varilla 3/8 x 6m | und | 18500 | 300",
    ]


def test_excel_va_como_texto_y_pdf_como_archivo():
    ai = FakeAI()
    asyncio.run(extract_json_from_upload(ai, "catalogo.xlsx", _xlsx({"H": [["Cemento", 1]]}), "instr"))
    asyncio.run(extract_json_from_upload(ai, "cotizacion.PDF", b"%PDF-1.4", "instr"))
    assert ai.calls[0][0] == "texto" and "Cemento | 1" in ai.calls[0][1]
    assert ai.calls[1] == ("archivo", "application/pdf")


@pytest.mark.parametrize("filename, content, message", [
    ("viejo.xls", b"xx", ".xls"),
    ("notas.docx", b"xx", "Formato no compatible"),
    ("vacio.pdf", b"", "vacío"),
    ("danado.xlsx", b"no es un excel", "No se pudo leer"),
])
def test_archivos_no_validos_dan_un_error_claro(filename, content, message):
    with pytest.raises(ValidationError, match=message):
        asyncio.run(extract_json_from_upload(FakeAI(), filename, content, "instr"))
