import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

import streamlit as st
from PIL import Image
import pdf2image
import re
import tempfile

POPPLER_PATH = r"C:\poppler-24.08.0\Library\bin"

# ----------------------- Esquema SQL -------------------------
SQL_SCHEMA = """
**Clientes**
- id (PK)
- nombre
- direccion

**Facturas**
- numero (PK)
- fecha
- subtotal
- iva
- total
- cliente_id (FK → Clientes.id)

**ItemsFactura**
- id (PK, opcional)
- factura_numero (FK → Facturas.numero)
- descripcion
- cantidad
- precio
"""

# ------------------- Streamlit PAGE CONFIG -------------------

st.set_page_config(page_title="Facturas a Script SQL", page_icon="🧾", layout="wide")

# ---------- SIDEBAR (Navbar) con Esquema y Branding ----------
with st.sidebar:
    st.markdown("# 🧾 Esquema SQL")
    st.markdown(SQL_SCHEMA)
    st.markdown("---")
    st.markdown("### Proyecto de Curso")
    st.markdown("Lenguajes de Programación")
    st.markdown("**Universidad de los Llanos - 2025**")
    st.markdown("**Integrantes:**")
    st.markdown("- Luis Alfonso Medina Romero  \n- Anggy Michelle Marin Alfonso  \n- Jhonnathan Stiven Villarraga Ariza")
    st.markdown("Licencia: [MIT](https://opensource.org/licenses/MIT)")
    st.markdown("---")

# ------------------- TÍTULO Y DESCRIPCIÓN --------------------
st.markdown(
    "<h1 style='color:#b7f9f7;'>App web: Facturas a Script SQL</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    """
    <p style='font-size:18px;'>
    Esta aplicación te permite cargar facturas (imagen o PDF), extraer automáticamente los datos relevantes usando <b>OCR</b> y expresiones regulares (Español/Inglés), y generar scripts <b>SQL</b> listos para poblar tu base de datos.<br>
    <br>
    <b>¡Automatiza tu registro de facturas de manera sencilla y segura!</b>
    </p>
    """, unsafe_allow_html=True
)

st.markdown("----")

# ------------------ PATRONES Y FUNCIONES OCR -----------------

FIELD_PATTERNS = {
    "cliente_id": [
        r"(NIT|RUC|CIF|Cédula|Identificación|ID|CC|Cliente ID|Identificación No\.?|Doc\. No\.?)\s*[:\-]?\s*([A-Za-z0-9\-\.]+)",
        r"(Customer ID|Client ID|ID|Identification|Document No\.?)\s*[:\-]?\s*([A-Za-z0-9\-\.]+)"
    ],
    "cliente_nombre": [
        r"(Nombre|Cliente|Raz[oó]n Social|A nombre de|Sr(a)?|Name|Customer|Client|Business Name|To the name of|Mr\.?|Ms\.?)\s*[:\-]?\s*(.+)",
    ],
    "cliente_direccion": [
        r"(Direcci[oó]n|Domicilio|Direcci[oó]n de entrega|Ubicaci[oó]n|Address|Delivery Address|Location)\s*[:\-]?\s*(.+)"
    ],
    "factura_numero": [
        r"(N[úu]mero|No\.?|Factura No\.?|No\. Factura|N° Factura|Invoice Number|Number|No\.|Invoice)\s*[:\-]?\s*([A-Za-z0-9\-\.]+)"
    ],
    "factura_fecha": [
        r"(Fecha|Fecha de emisi[oó]n|Date|Issue Date|Emitted on)\s*[:\-]?\s*([0-9]{2,4}[-/][0-9]{1,2}[-/][0-9]{1,2})"
    ],
    "factura_subtotal": [
        r"(Subtotal|Valor antes de impuestos|Base imponible|Subtotal Amount|Base Amount|Sub-Total)\s*[:\-]?\s*\$?\s*([\d.,]+)"
    ],
    "factura_iva": [
        r"(IVA|Impuesto|Valor IVA|VAT|I\.V\.A\.|Tax)\s*[:\-]?\s*\$?\s*([\d.,]+)"
    ],
    "factura_total": [
        r"(Total|Total a pagar|Valor total|Importe total|Grand Total|Total Amount|Amount Due|Total to pay)\s*[:\-]?\s*\$?\s*([\d.,]+)"
    ],
}

ITEMS_HEADER_VARIANTS = [
    ["Descripci[oó]n", "Cantidad", "Precio"],
    ["Concepto", "Cantidad", "Valor"],
    ["Producto", "Cantidad", "Precio"],
    ["Description", "Quantity", "Price"],
    ["Item", "Qty", "Price"],
    ["Concept", "Quantity", "Value"]
]

def extract_text_from_image(img):
    text_spa = pytesseract.image_to_string(img, lang="spa")
    text_eng = pytesseract.image_to_string(img, lang="eng")
    return text_spa if len(text_spa.split()) > len(text_eng.split()) else text_eng

def extract_text_from_pdf(pdf_file):
    with tempfile.TemporaryDirectory() as path:
        images = pdf2image.convert_from_bytes(
            pdf_file.read(),
            output_folder=path,
            poppler_path=POPPLER_PATH
        )
        text_spa, text_eng = "", ""
        for image in images:
            text_spa += pytesseract.image_to_string(image, lang="spa") + "\n"
            text_eng += pytesseract.image_to_string(image, lang="eng") + "\n"
    return text_spa if len(text_spa.split()) > len(text_eng.split()) else text_eng

def extract_field(patterns, text, group=2):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value = match.group(group)
                if value is not None:
                    return value.strip()
            except IndexError:
                pass
            try:
                value = match.groups()[-1]
                if value is not None:
                    return value.strip()
            except Exception:
                pass
            try:
                return match.group(0).strip()
            except Exception:
                pass
    return "NA"

def extract_fields(text):
    warnings = []
    data = {
        "cliente_id": "NA",
        "cliente_nombre": "NA",
        "cliente_direccion": "NA",
        "factura_numero": "NA",
        "factura_fecha": "NA",
        "factura_subtotal": "NA",
        "factura_iva": "NA",
        "factura_total": "NA",
        "items": []
    }

    for key, patterns in FIELD_PATTERNS.items():
        value = extract_field(patterns, text)
        data[key] = value
        if value == "NA":
            warnings.append(f"No se pudo extraer el campo: {key.replace('_', ' ').capitalize()}.")

    items = []
    lines = text.splitlines()
    header_idx = -1
    headers = []
    for idx, line in enumerate(lines):
        for variant in ITEMS_HEADER_VARIANTS:
            if all(re.search(v, line, re.IGNORECASE) for v in variant):
                header_idx = idx
                headers = variant
                break
        if header_idx != -1:
            break
    if header_idx != -1 and headers:
        col_positions = []
        for h in headers:
            match = re.search(h, lines[header_idx], re.IGNORECASE)
            if match:
                col_positions.append(match.start())
            else:
                col_positions.append(None)
        for item_line in lines[header_idx+1:]:
            if not item_line.strip() or re.match(r"(-{3,}|\={3,})", item_line):
                break
            row = []
            for i, pos in enumerate(col_positions):
                if pos is not None:
                    if i == len(col_positions)-1:
                        row.append(item_line[pos:].strip())
                    else:
                        next_pos = col_positions[i+1] if col_positions[i+1] is not None else len(item_line)
                        row.append(item_line[pos:next_pos].strip())
            if len(row) >= 3:
                descripcion = row[0] if row[0] else "NA"
                cantidad = re.search(r"[\d]+", row[1]) or re.search(r"[\d]+", row[2])
                precio = re.search(r"[\d.,]+", row[2]) or re.search(r"[\d.,]+", row[1])
                items.append({
                    "descripcion": descripcion,
                    "cantidad": cantidad.group() if cantidad else "NA",
                    "precio": precio.group().replace(',', '') if precio else "NA"
                })
        if not items:
            warnings.append("No se pudieron extraer los ítems de la factura.")
        data["items"] = items
    else:
        items_pattern = re.compile(
            r"(.+?)\s{2,}(\d+)\s{2,}\$?([\d.,]+)", re.MULTILINE
        )
        items = [
            {"descripcion": desc.strip() if desc else "NA",
             "cantidad": cant if cant else "NA",
             "precio": precio.replace(',', '') if precio else "NA"}
            for desc, cant, precio in items_pattern.findall(text)
        ]
        if items:
            data["items"] = items
        else:
            warnings.append("No se pudieron extraer los ítems de la factura.")

    return data, warnings

def generate_sql_script(data):
    sql = "-- Script generado automáticamente por App Facturas a Script SQL\n\n"
    sql += f"INSERT INTO clientes (id, nombre, direccion) VALUES ('{data['cliente_id']}', '{data['cliente_nombre']}', '{data['cliente_direccion']}');\n"
    sql += (f"INSERT INTO facturas (numero, fecha, subtotal, iva, total, cliente_id) VALUES "
            f"('{data['factura_numero']}', '{data['factura_fecha']}', {data['factura_subtotal'] if data['factura_subtotal'] != 'NA' else 'NULL'}, "
            f"{data['factura_iva'] if data['factura_iva'] != 'NA' else 'NULL'}, {data['factura_total'] if data['factura_total'] != 'NA' else 'NULL'}, '{data['cliente_id']}');\n")
    for item in data["items"]:
        sql += (f"INSERT INTO items_factura (factura_numero, descripcion, cantidad, precio) VALUES "
                f"('{data['factura_numero']}', '{item['descripcion']}', {item['cantidad'] if item['cantidad'] != 'NA' else 'NULL'}, {item['precio'] if item['precio'] != 'NA' else 'NULL'});\n")
    return sql

# ------------------- SECCIÓN PRINCIPAL -----------------------

st.markdown("## 1️⃣ Cargar factura")
uploaded_file = st.file_uploader(
    "Selecciona una factura en formato imagen (.jpg, .png) o PDF:",
    type=["jpg", "jpeg", "png", "pdf"]
)

if uploaded_file:
    filetype = uploaded_file.type
    st.markdown("#### Vista previa del archivo:")
    if filetype in ["image/jpeg", "image/png"]:
        image = Image.open(uploaded_file)
        st.image(image, caption="Factura cargada", use_container_width=True)
        text = extract_text_from_image(image)
    elif filetype == "application/pdf":
        text = extract_text_from_pdf(uploaded_file)
        st.success("PDF procesado correctamente.")
    else:
        st.error("Formato no soportado.")
        text = ""

    if text:
        st.markdown("## 2️⃣ Resultado del OCR")
        st.text_area("Texto extraído automáticamente (OCR):", value=text, height=200)

        st.markdown("## 3️⃣ Procesamiento y extracción de datos")
        data, warnings = extract_fields(text)

        st.write("### Datos identificados de la factura")
        st.json(data)

        if warnings:
            st.warning("Advertencias encontradas:\n- " + "\n- ".join(warnings))
        else:
            st.success("✅ Todos los campos se extrajeron correctamente.")

        st.markdown("---")
        st.markdown("## 4️⃣ Script SQL generado")
        if st.button("Generar Script SQL"):
            sql_script = generate_sql_script(data)
            st.code(sql_script, language="sql")
            st.download_button(
                label="Descargar script SQL",
                data=sql_script,
                file_name="factura_script.sql",
                mime="text/plain"
            )
else:
    st.info("Por favor, carga una factura para comenzar.")

st.markdown("----")
