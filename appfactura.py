import streamlit as st
from PIL import Image
import pytesseract
import re
import pandas as pd
import os # Importar el módulo os

# --- Configuración de Tesseract ---
# Especificar la ruta al ejecutable de Tesseract:
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe' # Ruta para Windows

# Especificar la ruta al directorio que CONTIENE la carpeta 'tessdata'
# Esto es crucial si Tesseract no encuentra los archivos de idioma.
tessdata_dir_config = r'--tessdata-dir "C:/Program Files/Tesseract-OCR/tessdata/"'
# Alternativamente, configurar la variable de entorno TESSDATA_PREFIX
#os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR'


# --- Funciones de Extracción con Expresiones Regulares (Modelos de Autómatas Finitos) ---

def extraer_texto_de_imagen(imagen_pil):
    """
    Utiliza Tesseract OCR para extraer texto de una imagen.
    """
    try:
        # Usar el idioma español para el OCR puede mejorar la precisión para facturas en español.
        # Añadir la configuración de tessdata_dir_config a image_to_string
        texto = pytesseract.image_to_string(imagen_pil, lang='spa', config=tessdata_dir_config)
        return texto
    except Exception as e:
        st.error(f"Error durante el OCR: {e}")
        st.error("Asegúrate de que Tesseract OCR y los datos del idioma español ('spa.traineddata') estén instalados correctamente.")
        st.error(f"Verifica que 'spa.traineddata' exista en: C:\\Program Files\\Tesseract-OCR\\tessdata\\")
        st.error("Verifica que la ruta en el script a 'tesseract.exe' y 'TESSDATA_PREFIX' sean correctas.")
        st.error("Puedes descargar 'spa.traineddata' desde: https://github.com/tesseract-ocr/tessdata")
        return None

def extraer_numero_factura(texto):
    """
    Extrae el número de factura usando expresiones regulares.
    Esta expresión busca patrones comunes para números de factura.
    """
    # Patrones posibles: "Factura N°", "Factura:", "N° Factura", "Invoice No.", etc. seguido de números y letras.
    # Se añade "FACTURA PRO FORMA" y patrones más específicos para la imagen de ejemplo
    patrones = [
        r'(?:Factura\s*N[o°º\.\s:]*|FACTURA\s*N[o°º\.\s:]*|Invoice\s*No\.*\s*:*\s*|N[o°º\.\s:]*F\s*A\s*C\s*T\s*U\s*R\s*A|FACTURA\s*PRO\s*FORMA)\s*([A-Za-z0-9\-]+)',
        r'N[o°º\.\s:]*\s*([A-Za-z0-9\-]{3,})', # Un número/código más genérico que podría ser el de factura
        r'FACTURA\s+([A-Z0-9\-]+)',
        r'FACTURA\s*PRO\s*FORMA' # Para capturar el tipo si no hay número específico
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            # Si el grupo 1 existe (es decir, se capturó un número), devuélvelo.
            # Si no, y el patrón era 'FACTURA PRO FORMA', devuelve eso como indicador.
            if match.lastindex and match.lastindex >=1:
                 return match.group(1).strip() if match.group(1) else "PRO FORMA" # Devolver PRO FORMA si no hay número
            elif "PRO FORMA" in match.group(0).upper(): # Si el match fue solo "FACTURA PRO FORMA"
                return "PRO FORMA" # O un identificador que prefieras
    return None


def extraer_fecha_factura(texto):
    """
    Extrae la fecha de la factura usando expresiones regulares.
    Busca formatos comunes de fecha (dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd, etc.).
    """
    # Priorizar formatos más específicos primero
    # Añadido patrón para "Madrid , a 20 de marzo de 2013"
    patrones = [
        r'Fecha\s*(?:factura)?\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'Date\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'(?:[A-Za-zÁÉÍÓÚÑáéíóúñ\s]+,\s*a\s*)?(\d{1,2}\s*(?:de|del)\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]+\s*(?:de|del)\s*\d{2,4})', # Ej: Madrid , a 20 de Enero de 2023
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', # Formato genérico dd/mm/yy o dd/mm/yyyy
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'  # Formato yyyy/mm/dd
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            # Si el grupo específico para fechas con mes en texto existe y tiene contenido
            if len(match.groups()) > 0 and match.group(1) and any(c.isalpha() for c in match.group(1)):
                return match.group(1).strip()
            # Para otros formatos numéricos
            elif len(match.groups()) > 0 and match.group(1):
                 return match.group(1).strip()
    return None

def extraer_total_factura(texto):
    """
    Extrae el total de la factura usando expresiones regulares.
    Busca palabras clave como "Total", "TOTAL", "Importe Total" seguido de un monto.
    """
    # Patrones para el total. Considera diferentes separadores decimales y de miles.
    # Ajustado para "TOTAL FACTURA PRO FORMA 1.627,45 C" (la C es un error de OCR para €)
    patrones = [
        r'(?:TOTAL\s*A\s*PAGAR|TOTAL\s*FACTURA(?:\s*PRO\s*FORMA)?|Total\s*EUR|Importe\s*Total|Total|TOTAL)\s*:?\s*[$€]?\s*([0-9\.,]+\d)\s*(?:[€CE])?',
        r'Total\s*:?\s*([0-9\.,]+\d)\s*(?:[€CE])?'
    ]
    monto_max = -1.0 # Inicializar con un flotante
    val_max_str = None

    for patron in patrones:
        matches = re.finditer(patron, texto, re.IGNORECASE)
        for match in matches:
            val_str = match.group(1)
            # Limpiar y convertir el valor.
            val_str_cleaned_miles = val_str.replace('.', '')
            val_str_cleaned_decimal = val_str_cleaned_miles.replace(',', '.')

            try:
                current_float = float(val_str_cleaned_decimal)
                if current_float > monto_max:
                    monto_max = current_float
                    val_max_str = val_str
            except ValueError:
                val_str_cleaned_miles_alt = val_str.replace(',', '')
                try:
                    current_float = float(val_str_cleaned_miles_alt)
                    if current_float > monto_max:
                        monto_max = current_float
                        val_max_str = val_str
                except ValueError:
                    continue

    if val_max_str is not None:
        return monto_max

    # Fallback si la conversión a float falló pero se encontraron patrones
    # Esta sección es un poco compleja y podría simplificarse o eliminarse si la conversión anterior es suficiente
    all_text_matches = []
    for patron_inner in patrones:
        # re.findall devuelve una lista de strings (o tuplas si hay múltiples grupos)
        found = re.findall(patron_inner, texto, re.IGNORECASE)
        for item in found:
            if isinstance(item, tuple): # Si es una tupla, tomar el primer elemento
                all_text_matches.append(item[0])
            else:
                all_text_matches.append(item)
    
    if all_text_matches:
        return all_text_matches[-1] # Devolver el último string encontrado como fallback

    return None


def extraer_nombre_vendedor(texto):
    """
    Intenta extraer el nombre del vendedor. Esto es muy variable.
    Podría buscarse cerca de NIF/CIF del vendedor o en la cabecera.
    Para la factura de ejemplo: "Pedro Prueba Probando"
    """
    lineas = texto.split('\n')
    posibles_nombres = []

    for i, linea in enumerate(lineas):
        linea_limpia = linea.strip()
        if i < 5 and len(linea_limpia) > 5 and \
           not any(keyword in linea_limpia.upper() for keyword in ["FACTURA", "CLIENTE", "NIF", "CIF", "DIRECCIÓN", "TELÉFONOS", "CORREO"]) and \
           any(c.isalpha() for c in linea_limpia) and \
           linea_limpia.upper() == linea_limpia:
            if not re.search(r'\d{5,}', linea_limpia) and not "@" in linea_limpia:
                posibles_nombres.append(linea_limpia)
                break 

        if "NIF" in linea_limpia.upper() and i > 0:
            linea_anterior = lineas[i-1].strip()
            if len(linea_anterior) > 5 and any(c.isalpha() for c in linea_anterior) and \
               not any(keyword in linea_anterior.upper() for keyword in ["FACTURA", "CLIENTE"]):
                posibles_nombres.append(linea_anterior)
                break
    
    if posibles_nombres:
        return posibles_nombres[0]

    match = re.search(r'^(?!FACTURA\b|CLIENTE\b)([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\s,S.L. S.A.]{4,})\n', texto, re.MULTILINE)
    if match:
        return match.group(1).strip()
    match_keyword = re.search(r'(?:Vendedor|Emitido por)\s*:\s*(.+)', texto, re.IGNORECASE)
    if match_keyword:
        return match_keyword.group(1).strip().split('\n')[0]
    return "No detectado"


def extraer_nombre_cliente(texto):
    """
    Intenta extraer el nombre del cliente.
    Para la factura de ejemplo: "GESTORES Y ASOCIADOS S.L."
    """
    patrones = [
        r'(?:CLIENTE\s*:|Cliente\s*:|Señor\(es\)\s*:|Destinatario\s*:|Comprador\s*:)\s*([^\n]+)',
        r'CLIENTE\s*:\s*\n\s*([A-ZÁÉÍÓÚÑ\sS.L.S.A.]{5,})\s*\n\s*(?:CIF|Dirección)',
        r'CLIENTE\s*:\s*([A-ZÁÉÍÓÚÑ\sS.L.S.A.]{5,})'
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if match:
            nombre = match.group(1).strip()
            nombre = re.sub(r'\s*CIF\s*:.*', '', nombre, flags=re.IGNORECASE)
            nombre = re.sub(r'\s*Dirección\s*:.*', '', nombre, flags=re.IGNORECASE)
            return nombre.strip()
    return "No detectado"

def extraer_items_factura(texto):
    """
    Intenta extraer los ítems de la factura. Este es el paso más complejo
    y altamente dependiente del formato de la factura.
    Implementación mejorada para la factura de ejemplo.
    """
    items = []
    lineas = texto.split('\n')
    en_seccion_items = False
    keywords_inicio_items = ["CONCEPTO :", "Trabajo :", "Descripción", "Concepto", "Details", "Item", "Producto", "DESCRIPTION"]
    keywords_fin_items = ["Total", "SUBTOTAL", "BASE IMPONIBLE", "IVA", "IMPORTE :", "TOTAL", "VAT"]
    
    regex_item_line = re.compile(
        r"^(.*?)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)$"
    )
    regex_descripcion_continua = re.compile(r"^\s*([A-Za-zÀ-ÖØ-öø-ÿ0-9\s\(\)\-:\.,'%]+?)\s*$") # Permitir números y % en descripciones
    descripcion_buffer = ""

    for i, linea in enumerate(lineas):
        linea_limpia = linea.strip()

        if not en_seccion_items:
            for keyword in keywords_inicio_items:
                if keyword.lower() in linea_limpia.lower():
                    en_seccion_items = True
                    # Si la keyword es la única cosa en la línea, o parte de ella, no la añadas al buffer de descripción
                    # Ejemplo: "CONCEPTO :" no debe ser parte de la descripción del primer ítem.
                    # Si la línea es SOLO la keyword (con espacios opcionales), saltar al siguiente.
                    if linea_limpia.lower() == keyword.lower():
                        descripcion_buffer = "" # Limpiar buffer por si acaso
                        continue # Pasar a la siguiente línea que podría ser el ítem
                    # Si la keyword está al inicio de la línea, intentar removerla para el procesamiento del ítem
                    # Esto es riesgoso si la keyword es parte de una descripción real.
                    # Por ahora, se asume que si la keyword está, la línea es cabecera o el regex_item_line lo manejará.
                    break 
            if not en_seccion_items:
                continue
        
        # Comprobar si hemos llegado al final de la sección de ítems
        # Es importante hacer esto *antes* de procesar la línea como un ítem
        # para evitar que líneas como "SUBTOTAL ..." se procesen como ítems.
        for keyword_fin in keywords_fin_items:
            # Si la línea COMIENZA con una keyword de fin (ignorando mayúsculas/minúsculas y espacios)
            if linea_limpia.lower().startswith(keyword_fin.lower()):
                en_seccion_items = False
                descripcion_buffer = "" 
                break 
        if not en_seccion_items: # Si se marcó el fin de la sección, salir del bucle de ítems
            break


        match = regex_item_line.match(linea_limpia)
        if match:
            descripcion_actual = match.group(1).strip()
            if descripcion_buffer:
                # Si el buffer no es solo una keyword de cabecera
                if not any(keyword.lower() in descripcion_buffer.lower() for keyword in keywords_inicio_items if len(descripcion_buffer.split()) < 3):
                    descripcion = descripcion_buffer + " " + descripcion_actual
                else: # El buffer era probablemente una cabecera
                    descripcion = descripcion_actual
                descripcion_buffer = ""
            else:
                descripcion = descripcion_actual
            
            precio_unitario_str = match.group(2)
            unidades_str = match.group(3)
            precio_total_str = match.group(4)

            def limpiar_numero(num_str):
                cleaned = num_str.replace('.', '').replace(',', '.')
                # Intentar manejar casos como "9.00" (OCR de 9,00) o "35,00" (OCR de 35.00)
                # Si después de la limpieza inicial sigue habiendo un punto y es el único, está bien.
                # Si hay más de un punto, es probable que el primer replace (quitar '.') fuera incorrecto para ese número.
                # Esta lógica puede volverse compleja. Una heurística simple:
                # Si el original tenía comas y no puntos (o el último punto era antes de la última coma),
                # entonces la coma era decimal.
                # Si el original tenía puntos y no comas (o la última coma era antes del último punto),
                # entonces el punto era decimal.
                # Por simplicidad, el replace actual es un intento genérico.
                return cleaned

            items.append({
                "descripcion": descripcion.replace(":", "").strip(),
                "cantidad": limpiar_numero(unidades_str),
                "precio_unitario": limpiar_numero(precio_unitario_str),
                "precio_total_item": limpiar_numero(precio_total_str)
            })
        else: # No es una línea de ítem completa
            # Evitar que cabeceras de tabla se añadan al buffer de descripción
            if not any(hdr.lower() in linea_limpia.lower() for hdr in ["precio", "unitario", "unidades", "total", "cantidad", "descripción", "importe", "unit", "price", "qty", "amount"]) and \
               len(linea_limpia) > 3: # Ignorar líneas muy cortas
                match_desc_cont = regex_descripcion_continua.match(linea_limpia)
                if match_desc_cont:
                    if descripcion_buffer:
                        descripcion_buffer += " " + linea_limpia
                    else:
                        descripcion_buffer = linea_limpia
            elif not linea_limpia: # Línea vacía
                 descripcion_buffer = ""


    items_filtrados = [
        item for item in items
        if not any(hdr.lower() in item["descripcion"].lower() for hdr in ["materiales", "mano de obra"]) or len(item["descripcion"].split()) > 2
    ]
    if items and not items_filtrados: # Si el filtro eliminó todo pero había ítems, devolver los originales
        return items
    return items_filtrados


# --- Funciones de Generación de SQL ---

def generar_sql_insert(datos_factura, items_factura):
    """
    Genera sentencias SQL INSERT para los datos extraídos.
    """
    sql_statements = []

    num_factura_val = datos_factura.get('numero_factura', 'NULL')
    num_factura = f"'{num_factura_val}'" if num_factura_val != 'NULL' and num_factura_val is not None else 'NULL'
    
    fecha_factura_val = datos_factura.get('fecha_factura', 'NULL')
    fecha_factura = f"'{fecha_factura_val}'" if fecha_factura_val != 'NULL' and fecha_factura_val is not None else 'NULL'
    
    nombre_vendedor_val = datos_factura.get('nombre_vendedor', 'No Detectado')
    nombre_vendedor = f"'{nombre_vendedor_val.replace("'", "''")}'" if nombre_vendedor_val else "'No Detectado'"

    nombre_cliente_val = datos_factura.get('nombre_cliente', 'No Detectado')
    nombre_cliente = f"'{nombre_cliente_val.replace("'", "''")}'" if nombre_cliente_val else "'No Detectado'"

    total_factura_val = datos_factura.get('total_factura') # No poner default aquí
    total_factura_sql = "NULL" # Default para SQL
    if total_factura_val is not None:
        try:
            total_factura_sql = f"{float(total_factura_val):.2f}" # Formatear a 2 decimales
        except (ValueError, TypeError):
            # Si la conversión falla, intentar limpiar comas/puntos y convertir de nuevo
            try:
                cleaned_total = str(total_factura_val).replace('.', '').replace(',', '.')
                total_factura_sql = f"{float(cleaned_total):.2f}"
            except (ValueError, TypeError):
                total_factura_sql = "NULL" # Mantener como NULL si todo falla

    factura_id_para_items = num_factura 

    sql_factura = f"""
INSERT INTO Facturas (NumeroFactura, FechaFactura, NombreVendedor, NombreCliente, TotalFactura)
VALUES ({num_factura}, {fecha_factura}, {nombre_vendedor}, {nombre_cliente}, {total_factura_sql});
"""
    sql_statements.append("-- Insertar datos de la Factura")
    sql_statements.append(sql_factura)
    sql_statements.append("\n-- Insertar ítems de la Factura")
    sql_statements.append(f"-- ASOCIADOS A LA FACTURA: {num_factura_val if num_factura_val not in ['NULL', None] else 'DESCONOCIDA'}\n")

    if items_factura:
        for item in items_factura:
            descripcion_val = item.get('descripcion', 'N/A')
            descripcion = f"'{descripcion_val.replace("'", "''")}'"

            def format_decimal_sql(val_str, default_val=0.0):
                if val_str is None: return f"{default_val:.2f}"
                try:
                    # Primero, intentar convertir directamente si es un número
                    return f"{float(val_str):.2f}"
                except ValueError:
                    # Si falla, intentar limpiar (asumiendo formato europeo primero)
                    cleaned_val = str(val_str).replace('.', '').replace(',', '.')
                    try:
                        return f"{float(cleaned_val):.2f}"
                    except ValueError:
                         # Intentar formato americano como fallback
                        cleaned_val_alt = str(val_str).replace(',', '')
                        try:
                            return f"{float(cleaned_val_alt):.2f}"
                        except ValueError:
                             return f"{default_val:.2f}" # Fallback final

            cantidad_sql = format_decimal_sql(item.get('cantidad', '0'), 0.0)
            precio_unitario_sql = format_decimal_sql(item.get('precio_unitario', '0'), 0.0)
            precio_total_item_sql = format_decimal_sql(item.get('precio_total_item', '0'), 0.0)
            
            sql_item = f"""
INSERT INTO ItemsFactura (InvoiceID_FK, DescripcionItem, Cantidad, PrecioUnitario, PrecioTotalItem)
VALUES ({factura_id_para_items}, {descripcion}, {cantidad_sql}, {precio_unitario_sql}, {precio_total_item_sql});
"""
            sql_statements.append(sql_item)
    else:
        sql_statements.append("-- No se detectaron ítems o hubo un error en su extracción.")

    return "\n".join(sql_statements)

# --- Interfaz de Streamlit ---
st.set_page_config(layout="wide", page_title="Factura a SQL")

st.title("📄 Conversor de Imagen de Factura a Script SQL 💾")
st.markdown("""
Sube una imagen de una factura y esta aplicación intentará extraer la información relevante
usando OCR (Tesseract) y **Expresiones Regulares** (basadas en la teoría de **Autómatas Finitos**)
para generar un script SQL.

**Nota:** La precisión de la extracción depende en gran medida de la calidad de la imagen,
la claridad del texto, el idioma y el formato de la factura. Este es un prototipo y
las expresiones regulares pueden necesitar ajustes para diferentes tipos de facturas.
Se han realizado ajustes para intentar procesar la factura de ejemplo proporcionada.
""")

#st.write(pytesseract.get_languages(config=''))

st.sidebar.header("Cargar Factura")
archivo_subido = st.sidebar.file_uploader("Selecciona una imagen de la factura", type=["png", "jpg", "jpeg", "pdf"])

st.sidebar.subheader("Esquema SQL de Ejemplo:")
st.sidebar.code("""
CREATE TABLE Facturas (
    InvoiceID SERIAL PRIMARY KEY,
    NumeroFactura VARCHAR(255) UNIQUE,
    FechaFactura TEXT, 
    NombreVendedor TEXT,
    NombreCliente TEXT,
    TotalFactura DECIMAL(12,2) 
);

CREATE TABLE ItemsFactura (
    ItemID SERIAL PRIMARY KEY,
    InvoiceID_FK VARCHAR(255), 
    DescripcionItem TEXT,
    Cantidad NUMERIC(10,2), 
    PrecioUnitario DECIMAL(12,2), 
    PrecioTotalItem DECIMAL(12,2) 
);
""", language="sql")


if archivo_subido is not None:
    imagen = Image.open(archivo_subido)
    st.image(imagen, caption="Factura Subida", use_container_width=True)

    st.subheader("1. Texto Extraído con OCR (Tesseract)")
    with st.spinner("Procesando imagen y extrayendo texto... Esto puede tardar unos segundos."):
        texto_extraido = extraer_texto_de_imagen(imagen)

    if texto_extraido:
        st.text_area("Texto Completo Detectado", texto_extraido, height=300)

        st.subheader("2. Información Extraída (Usando Expresiones Regulares)")
        with st.spinner("Analizando texto y extrayendo campos clave..."):
            datos_factura = {}
            datos_factura['numero_factura'] = extraer_numero_factura(texto_extraido)
            datos_factura['fecha_factura'] = extraer_fecha_factura(texto_extraido)
            datos_factura['total_factura'] = extraer_total_factura(texto_extraido)
            datos_factura['nombre_vendedor'] = extraer_nombre_vendedor(texto_extraido)
            datos_factura['nombre_cliente'] = extraer_nombre_cliente(texto_extraido)

            # Preparar datos para el DataFrame, manejando None para la tabla
            display_data = {k: (str(v) if v is not None else "No detectado/Error") for k, v in datos_factura.items()}
            df_datos_factura = pd.DataFrame([display_data.values()], index=display_data.keys(), columns=["Valor Detectado"])
            st.table(df_datos_factura)


            st.markdown("---")
            st.markdown("### Items de la Factura Detectados:")
            items = extraer_items_factura(texto_extraido)
            if items:
                df_items = pd.DataFrame(items)
                st.dataframe(df_items, use_container_width=True)
            else:
                st.warning("No se pudieron extraer ítems detallados de la factura o el formato no es reconocido.")
                st.markdown("""
                La extracción de ítems es la parte más compleja y depende mucho de la estructura tabular de la factura.
                Las expresiones regulares actuales son un intento mejorado para el formato de ejemplo.
                """)

        st.subheader("3. Script SQL Generado")
        with st.spinner("Generando script SQL..."):
            script_sql = generar_sql_insert(datos_factura, items)
            st.code(script_sql, language="sql")
            st.download_button(
                label="Descargar Script SQL",
                data=script_sql,
                file_name=f"factura_{datos_factura.get('numero_factura', 'desconocido')}.sql",
                mime="text/sql"
            )

        st.success("Proceso completado. Revisa el script SQL generado.")
        st.info("""
        **Próximos Pasos y Mejoras (Conceptos Avanzados):**
        * **Mejores Expresiones Regulares:** Continuar refinando las expresiones regulares.
        * **Preprocesamiento de Imagen:** Implementar técnicas de OpenCV para mejorar el OCR.
        * **Validación de Datos y Tipos:** Asegurar que los tipos de datos sean correctos antes de la inserción SQL.
        * **Extracción de Tablas (Items):** Investigar bibliotecas como `camelot-py` o `tabula-py` (para PDF) o algoritmos de detección de tablas en imágenes.
        * **Machine Learning (NER):** Para una solución más robusta y adaptable.
        """)

    else:
        st.error("No se pudo extraer texto de la imagen. Intenta con una imagen de mejor calidad o revisa la configuración de Tesseract y la ruta especificada en el script.")

else:
    st.info("Por favor, sube una imagen de una factura para comenzar.")

st.markdown("---")
st.markdown("Proyecto de Curso - Lenguajes de Programación.")
st.markdown("Universidad de los Llanos - 2025.")
st.markdown("Nombres de los integrantes:")
st.markdown("- **Luis Alfonso Medina Romero**")
st.markdown("- **Anggy Michelle Marin Alfonso**")   
st.markdown("- **Jhonnathan Stiven Villarraga Ariza**")   
