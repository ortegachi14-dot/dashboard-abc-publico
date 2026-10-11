# V08.2 — Club Tijuana | Participaciones Liga MX + Copa Promesas
# Objetivo: ejecutar en Pyto la extracción individual de los 126 jugadores
# y generar todas las participaciones de Apertura 2026 y Copa Promesas 2026-2027.
#
# Fuente maestra: CSV exportado de la Base Maestra de Notion
# Fuente estadística: URL individual de Liga MX almacenada en la Base Maestra
# Competiciones objetivo:
#   - Apertura 2026
#   - Copa Promesas 2026-2027
# Temporada objetivo: 2026-2027
#
# NOTA:
# Pyto puede tener problemas resolviendo el backend API de Liga MX.
# Esta versión trabaja directamente con el HTML de las fichas individuales,
# que fue el método validado en los pilotos V01-V04.

import csv
import html
import re
import time
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ============================================================
# CONFIGURACIÓN
# ============================================================

TEMPORADA_OBJETIVO = "2026-2027"
COMPETICIONES_OBJETIVO = {
    "apertura 2026",
    "copa promesas 2026-2027",
}

BASE_DIR = Path.cwd() / "V08_copa_promesas"
HTML_DIR = BASE_DIR / "jugadores"
DIAG_DIR = BASE_DIR / "diagnosticos"
OUT_DIR = BASE_DIR / "resultados"

TIMEOUT = 25
PAUSA_ENTRE_DESCARGAS = 1.0

# Si quieres probar primero con pocos jugadores:
# cambia a un número entero, por ejemplo 5 o 10.
# None = procesar los 126.
LIMITE_PRUEBA = None

# Pega aquí los 126 registros exportados de Notion si Pyto
# no tiene acceso directo a Notion.
#
# Formato por línea:
# codigo|jugador|categoria|posicion|fecha_nacimiento|edad|url
#
# El script también permite cargar un CSV externo:
# BASE_DIR / "notion_jugadores.csv"
#
SCRIPT_DIR = Path(__file__).resolve().parent
CSV_NOTION_CANDIDATOS = [
    BASE_DIR / "notion_jugadores.csv",
    SCRIPT_DIR / "notion_jugadores.csv",
    Path.home() / "Documents" / "notion_jugadores.csv",
    Path.cwd() / "notion_jugadores.csv",
]
CSV_NOTION_CANDIDATOS = list(dict.fromkeys(CSV_NOTION_CANDIDATOS))
CSV_NOTION = next(
    (p for p in CSV_NOTION_CANDIDATOS if p.is_file()),
    CSV_NOTION_CANDIDATOS[0]
)

COLUMNAS_NOTION = [
    "codigo",
    "jugador",
    "categoria",
    "posicion",
    "fecha_nacimiento",
    "edad",
    "url",
]

# ============================================================
# UTILIDADES
# ============================================================

def limpiar_texto(valor):
    if valor is None:
        return ""
    valor = html.unescape(str(valor))
    valor = re.sub(r"\s+", " ", valor)
    return valor.strip()


def normalizar(valor):
    valor = limpiar_texto(valor).lower()
    valor = unicodedata.normalize("NFD", valor)
    valor = "".join(c for c in valor if unicodedata.category(c) != "Mn")
    return valor


def entero(valor):
    if valor is None:
        return 0
    m = re.search(r"\d+", str(valor).replace(",", ""))
    return int(m.group()) if m else 0


def extraer_categoria_registro(url):
    if not url:
        return ""
    m = re.search(r"https?://(sub\d+)\.ligamx\.net", url, re.I)
    if not m:
        return ""
    mapa = {
        "sub15": "Sub 15",
        "sub17": "Sub 17",
        "sub19": "Sub 19",
        "sub21": "Sub 21",
    }
    return mapa.get(m.group(1).lower(), m.group(1).lower())


def extraer_id_liga(url):
    if not url:
        return ""
    m = re.search(r"/jugador/(\d+)", url)
    return m.group(1) if m else ""


def extraer_nui(texto):
    patrones = [
        r"NUI\s*[:\-]?\s*(\d+)",
        r"NUI[^0-9]{0,30}(\d+)",
        r"nui[^0-9]{0,30}(\d+)",
    ]
    for patron in patrones:
        m = re.search(patron, texto, re.I)
        if m:
            return m.group(1)
    return ""


def extraer_campo(texto, etiqueta):
    patron = rf"{re.escape(etiqueta)}\s*[:\-]?\s*([^<\n\r|]+)"
    m = re.search(patron, texto, re.I)
    return limpiar_texto(m.group(1)) if m else ""


def descargar(url):
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
            )
        },
    )
    with urlopen(req, timeout=TIMEOUT) as response:
        data = response.read()
        status = getattr(response, "status", 200)
        return status, data


# ============================================================
# CARGA DE NOTION
# ============================================================

def cargar_notion():
    """
    Pyto no debe depender de una API privada de Notion para esta prueba.
    Se usa un CSV exportado de la base maestra.

    El CSV compatible contiene:
    codigo,jugador,categoria,posicion,fecha_nacimiento,edad,url

    V06.2 conserva el código maestro literalmente (ej. FB-2) y deriva
    categoria_registro desde el subdominio de la URL, sin usarla para
    determinar la división estadística.
    """

    if not CSV_NOTION.exists():
        print()
        print("NO SE ENCONTRÓ EL ARCHIVO DE NOTION")
        print()
        print("Se buscó exactamente: notion_jugadores.csv")
        print("Ubicaciones revisadas:")
        for p in CSV_NOTION_CANDIDATOS:
            print(" -", p)
        print()
        print("Nombre: notion_jugadores.csv")
        print("Columnas:")
        print(",".join(COLUMNAS_NOTION))
        print()
        print("Después vuelve a ejecutar este script.")
        return []

    registros = []

    with CSV_NOTION.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            url = limpiar_texto(row.get("url", ""))

            registros.append({
                "codigo": limpiar_texto(row.get("codigo", "")),
                "jugador": limpiar_texto(row.get("jugador")),
                "categoria": limpiar_texto(row.get("categoria")),
                "posicion": limpiar_texto(row.get("posicion")),
                "fecha_nacimiento": limpiar_texto(row.get("fecha_nacimiento")),
                "edad": limpiar_texto(row.get("edad")),
                "url": url,
                "categoria_registro": extraer_categoria_registro(url),
                "id_liga_mx": extraer_id_liga(url),
            })

    return registros


# ============================================================
# REGLAS V08.2 — MULTICATEGORÍA
# ============================================================

JERARQUIA_CATEGORIA_MAESTRA = {
    "Sub 21": 1,
    "Sub 19": 2,
    "Sub 17": 3,
    "Sub 15": 4,
}

def normalizar_division(division):
    """
    Normaliza únicamente la etiqueta de división que se mostrará.
    LIGA MX se presenta como Primera División.
    """
    d = limpiar_texto(division)
    if normalizar(d) == "liga mx":
        return "Primera División"
    m = re.search(r"\bsub\s*(15|17|19|21)\b", d, re.I)
    if m:
        return "Sub " + m.group(1)
    return d

def categoria_estadistica_normalizada(division):
    """
    Conservada como helper interno para detectar movilidad entre
    categorías formativas. No se expone como columna independiente.
    """
    d = limpiar_texto(division)
    m = re.search(r"\bsub\s*(15|17|19|21)\b", d, re.I)
    return "Sub " + m.group(1) if m else ""

def es_multicategoria(categoria, division):
    cat_est = categoria_estadistica_normalizada(division)
    if not cat_est:
        return ""
    return "SI" if cat_est != limpiar_texto(categoria) else "NO"

# ============================================================
# EXTRACCIÓN DEL HISTÓRICO
# ============================================================

from html.parser import HTMLParser


class HistoricoTableParser(HTMLParser):
    """Parser estándar de biblioteca para la tabla histnacional1."""

    def __init__(self):
        self.in_table = False
        self.table_depth = 0
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.current_cell = []
        self.rows = []
        self.table_headers = []
        self.target_tables = 0
        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)
        if tag == "table":
            classes = (attrs_dict.get("class") or "").lower().split()
            if "histnacional1" in classes:
                self.in_table = True
                self.table_depth = 1
                self.target_tables += 1
                return
            if self.in_table:
                self.table_depth += 1
                return
        if not self.in_table:
            return
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = []
        self._tag_stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self.in_table:
            return
        if tag in ("td", "th") and self.in_cell:
            value = limpiar_texto(" ".join(self.current_cell))
            self.current_row.append(value)
            self.current_cell = []
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
            self.in_row = False
        elif tag == "table":
            if self.table_depth > 1:
                self.table_depth -= 1
            else:
                self.in_table = False
                self.table_depth = 0
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data):
        if self.in_table and self.in_cell:
            self.current_cell.append(data)


def parse_historico_rows(html_texto):
    from html.parser import HTMLParser
    parser = HistoricoTableParser()
    HTMLParser(convert_charrefs=True).feed(html_texto)
    # El objeto HTMLParser anterior no usa nuestros handlers; alimentamos
    # explícitamente la subclase para mantener compatibilidad con Pyto.
    parser = HistoricoTableParser()
    HTMLParser.__init__(parser, convert_charrefs=True)
    HTMLParser.feed(parser, html_texto)
    return parser.rows


def extraer_historicos(html_texto):
    """
    Devuelve TODAS las filas históricas de la temporada objetivo cuya
    competición sea Apertura 2026 o Copa Promesas 2026-2027.

    La fuente sigue siendo exclusivamente la ficha individual del jugador.
    No se consulta el portal estadístico de Copa Promesas.
    """
    try:
        filas = parse_historico_rows(html_texto)
    except Exception:
        filas = []

    temporada_obj = normalizar(TEMPORADA_OBJETIVO)
    salida = []

    for fila in filas:
        if len(fila) < 12:
            continue

        vals = [limpiar_texto(x) for x in fila[:12]]
        torneo_norm = normalizar(vals[2])
        temporada_norm = normalizar(vals[3])

        if temporada_norm != temporada_obj:
            continue
        if torneo_norm not in COMPETICIONES_OBJETIVO:
            continue

        try:
            salida.append({
                "fase": vals[0],
                "division": normalizar_division(vals[1]),
                "division_original": vals[1],
                "torneo": vals[2],
                "temporada": vals[3],
                "club": vals[4],
                "jj": entero(vals[5]),
                "mj": entero(vals[6]),
                "jt": entero(vals[7]),
                "g": entero(vals[8]),
                "ag": entero(vals[9]),
                "ta": entero(vals[10]),
                "tr": entero(vals[11]),
                "_fila": " | ".join(vals),
                "_parser": "histnacional1_htmlparser",
            })
        except Exception:
            continue

    return salida


# ============================================================
# PROCESAMIENTO INDIVIDUAL
# ============================================================

def procesar_jugador(registro, indice):
    jugador = registro["jugador"]
    url = registro["url"]
    id_liga = registro["id_liga_mx"]

    resultado = {
        "index": indice,
        "jugador": jugador,
        "codigo": registro["codigo"],
        "id_liga_mx": id_liga,
        "nui": "",
        "categoria": registro["categoria"],
        "categoria_registro": registro.get("categoria_registro", ""),
        "posicion": registro["posicion"],
        "fecha_nacimiento": registro["fecha_nacimiento"],
        "edad": registro["edad"],
        "url": url,
        "temporada": TEMPORADA_OBJETIVO,
        "num_participaciones": 0,
        "mj_total": 0,
        "estado_participacion": "",
        "http_status": "",
        "archivo_html": "",
        "error": "",
        "parser": "",
        "_participaciones": [],
    }

    if not url:
        resultado["estado_participacion"] = "ERROR"
        resultado["error"] = "URL_VACIA"
        return resultado

    nombre_archivo = f"{indice:03d}_{id_liga or registro['codigo']}.html"
    ruta_html = HTML_DIR / nombre_archivo
    resultado["archivo_html"] = str(ruta_html)

    try:
        status, data = descargar(url)
        resultado["http_status"] = status

        if status != 200:
            resultado["estado_participacion"] = "ERROR"
            resultado["error"] = f"HTTP_{status}"
            return resultado

        texto = data.decode("utf-8", errors="replace")
        ruta_html.write_text(texto, encoding="utf-8")
        resultado["nui"] = extraer_nui(texto)

        participaciones = extraer_historicos(texto)
        participaciones = deduplicar_participaciones([
            {
                "codigo": registro["codigo"],
                "jugador": registro["jugador"],
                "categoria": registro["categoria"],
                "temporada": p["temporada"],
                "competicion": p["torneo"],
                "fase": p["fase"],
                "division": p["division"],
                "club": p["club"],
                "jj": p["jj"],
                "mj": p["mj"],
                "jt": p["jt"],
                "g": p["g"],
                "ag": p["ag"],
                "ta": p["ta"],
                "tr": p["tr"],
            }
            for p in participaciones
        ])
        # Volver al formato interno original del parser.
        for p in participaciones:
            p["torneo"] = p["competicion"]
        resultado["_participaciones"] = participaciones
        resultado["num_participaciones"] = len(participaciones)
        resultado["mj_total"] = sum(p["mj"] for p in participaciones)

        if not participaciones:
            resultado["estado_participacion"] = "SIN_PARTICIPACION"
            return resultado

        resultado["parser"] = participaciones[0].get("_parser", "")
        resultado["estado_participacion"] = (
            "CON_MINUTOS" if resultado["mj_total"] > 0 else "SIN_MINUTOS"
        )

        return resultado

    except HTTPError as e:
        resultado["http_status"] = getattr(e, "code", "")
        resultado["estado_participacion"] = "ERROR"
        resultado["error"] = f"HTTP_ERROR_{getattr(e, 'code', '')}"
        return resultado

    except URLError as e:
        resultado["estado_participacion"] = "ERROR"
        resultado["error"] = f"URL_ERROR: {e}"
        return resultado

    except Exception as e:
        resultado["estado_participacion"] = "ERROR"
        resultado["error"] = f"{type(e).__name__}: {e}"
        return resultado




# ============================================================
# V08.2 — CONSOLIDACIÓN DE PARTICIPACIONES
# ============================================================

def _entero_seguro(v):
    try:
        return int(str(v).strip())
    except Exception:
        return 0

def clave_participacion(p):
    """
    Clave lógica de una participación.
    La COMPETICIÓN forma parte de la clave.
    Por ello, la misma división en dos competencias distintas
    se conserva como dos participaciones diferentes.
    """
    return (
        str(p.get("codigo", "")).strip(),
        str(p.get("temporada", "")).strip(),
        str(p.get("competicion", "")).strip(),
        str(p.get("fase", "")).strip(),
        str(p.get("division", "")).strip(),
        str(p.get("club", "")).strip(),
    )

def firma_participacion(p):
    return (
        clave_participacion(p),
        _entero_seguro(p.get("jj")),
        _entero_seguro(p.get("mj")),
        _entero_seguro(p.get("jt")),
        _entero_seguro(p.get("g")),
        _entero_seguro(p.get("ag")),
        _entero_seguro(p.get("ta")),
        _entero_seguro(p.get("tr")),
    )

def deduplicar_participaciones(p):
    """
    Elimina únicamente una fila que sea exactamente la misma
    participación estadística.

    NO elimina:
      Apertura 2026 / Sub 19
      Copa Promesas 2026-2027 / Sub 19
    """
    salida = []
    vistos = set()

    for fila in p:
        firma = firma_participacion(fila)
        if firma in vistos:
            continue
        vistos.add(firma)
        salida.append(fila)

    return salida

def resumir_por_division(participaciones):
    """
    Suma todas las competiciones dentro de una misma división.
    Las filas originales por competición permanecen intactas.

    Ejemplo:
      Sub 19 / Apertura 2026 = 450 MJ
      Sub 19 / Copa Promesas = 90 MJ
      Sub 19 total           = 540 MJ
    """
    acumulado = {}

    for p in participaciones:
        key = (
            p["codigo"],
            p["jugador"],
            p["categoria"],
            p["division"],
        )

        if key not in acumulado:
            acumulado[key] = {
                "codigo": p["codigo"],
                "jugador": p["jugador"],
                "categoria": p["categoria"],
                "division": p["division"],
                "competencias": 0,
                "jj": 0,
                "mj": 0,
                "jt": 0,
                "g": 0,
                "ag": 0,
                "ta": 0,
                "tr": 0,
            }

        x = acumulado[key]
        x["competencias"] += 1
        for c in ("jj", "mj", "jt", "g", "ag", "ta", "tr"):
            x[c] += _entero_seguro(p.get(c))

    return list(acumulado.values())


# ============================================================
# SALIDAS V08.2
# ============================================================

def guardar_csv(ruta, filas, columnas):
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filas)


COLUMNAS_PARTICIPACIONES = [
    "codigo", "jugador", "id_liga_mx", "nui",
    "categoria", "categoria_registro",
    "temporada", "competicion", "fase", "division",
    "club", "jj", "mj", "jt", "g", "ag", "ta", "tr",
    "multicategoria",
]

COLUMNAS_JUGADORES = [
    "codigo", "jugador", "id_liga_mx", "nui",
    "categoria", "categoria_registro", "posicion",
    "fecha_nacimiento", "edad", "url",
    "temporada", "mj_total", "num_participaciones",
    "estado_participacion", "http_status", "archivo_html",
    "error", "parser",
]

def generar_participaciones(resultados):
    salida = []
    for x in resultados:
        for p in x.get("_participaciones", []):
            salida.append({
                "codigo": x["codigo"],
                "jugador": x["jugador"],
                "id_liga_mx": x["id_liga_mx"],
                "nui": x["nui"],
                "categoria": x["categoria"],
                "categoria_registro": x["categoria_registro"],
                "temporada": p["temporada"],
                "competicion": p["torneo"],
                "fase": p["fase"],
                "division": p["division"],
                "club": p["club"],
                "jj": p["jj"],
                "mj": p["mj"],
                "jt": p["jt"],
                "g": p["g"],
                "ag": p["ag"],
                "ta": p["ta"],
                "tr": p["tr"],
                "multicategoria": es_multicategoria(x["categoria"], p["division"]),
            })
    guardar_csv(
        OUT_DIR / "participaciones.csv",
        salida,
        COLUMNAS_PARTICIPACIONES
    )
    return salida

def generar_resumen_competiciones(participaciones):
    acumulado = {}
    for p in participaciones:
        key = (p["competicion"], p["division"])
        if key not in acumulado:
            acumulado[key] = {"competicion": p["competicion"], "division": p["division"],
                               "jugadores": 0, "jj": 0, "mj": 0, "jt": 0, "g": 0,
                               "ag": 0, "ta": 0, "tr": 0}
        a = acumulado[key]
        a["jugadores"] += 1
        for c in ["jj","mj","jt","g","ag","ta","tr"]:
            a[c] += int(p[c] or 0)

    filas = list(acumulado.values())
    guardar_csv(
        OUT_DIR / "resumen_competencias.csv",
        filas,
        ["competicion","division","jugadores","jj","mj","jt","g","ag","ta","tr"]
    )

def main():
    for carpeta in [BASE_DIR, HTML_DIR, DIAG_DIR, OUT_DIR]:
        carpeta.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("V08.2 — PARTICIPACIONES | CLUB TIJUANA")
    print("Apertura 2026 + Copa Promesas 2026-2027")
    print("=" * 60)

    registros = cargar_notion()
    if not registros:
        return

    print(f"Jugadores cargados desde CSV maestro: {len(registros)}")

    if LIMITE_PRUEBA is not None:
        registros = registros[:LIMITE_PRUEBA]
        print(f"MODO PRUEBA: {len(registros)} jugadores")

    resultados = []

    for i, registro in enumerate(registros, 1):
        print(
            f"[{i}/{len(registros)}] "
            f"{registro['jugador']} | "
            f"{registro['categoria']}"
        )

        resultado = procesar_jugador(registro, i)
        resultados.append(resultado)

        print(
            f"    -> {resultado['estado_participacion']} | "
            f"Participaciones={resultado['num_participaciones']} | "
            f"MJ total={resultado['mj_total']}"
        )
        time.sleep(PAUSA_ENTRE_DESCARGAS)

    jugadores = []
    for x in resultados:
        jugadores.append({k: x.get(k, "") for k in COLUMNAS_JUGADORES})

    participaciones = generar_participaciones(resultados)

    # Resumen por competencia + división.
    generar_resumen_competiciones(participaciones)

    # Resumen por división, sumando todas las competencias sin
    # eliminar el detalle original.
    resumen_division = resumir_por_division(participaciones)
    guardar_csv(
        OUT_DIR / "participaciones_por_division.csv",
        resumen_division,
        [
            "codigo", "jugador", "categoria", "division",
            "competencias", "jj", "mj", "jt", "g", "ag", "ta", "tr"
        ],
    )

    guardar_csv(
        OUT_DIR / "jugadores_consolidados.csv",
        jugadores,
        COLUMNAS_JUGADORES
    )

    print()
    print("=" * 60)
    print("PROCESO TERMINADO")
    print("=" * 60)
    print(f"Resultados: {OUT_DIR}")
    print("Archivos:")
    print(" - jugadores_consolidados.csv")
    print(" - participaciones.csv")
    print(" - resumen_competencias.csv")
    print(" - participaciones_por_division.csv")
    print()
    print("Estados de jugadores:")
    for estado in ["CON_MINUTOS","SIN_MINUTOS","SIN_PARTICIPACION","ERROR"]:
        total = sum(1 for x in resultados if x["estado_participacion"] == estado)
        print(f" {estado}: {total}")
    print()
    print(f"Participaciones detectadas: {len(participaciones)}")
    print(f"Minutos totales detectados: {sum(int(p['mj'] or 0) for p in participaciones)}")

if __name__ == "__main__":
    main()
