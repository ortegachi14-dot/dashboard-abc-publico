import pandas as pd
from pathlib import Path
import numpy as np

# ============================================================
# V09 — PYTO
# Consolidación de minutos del Club Tijuana
# ============================================================

# Carpeta donde está este script:
BASE = Path(__file__).resolve().parent

# Los resultados V09 se guardan aquí, sin tocar los resultados V08.
OUTPUT_DIR = BASE / "V09_resultados"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _csv_candidates():
    """Todos los CSV disponibles dentro de Minutos FB."""
    return [
        p for p in BASE.rglob("*.csv")
        if OUTPUT_DIR not in p.parents
    ]


def find_input_file(kind):
    """
    Localiza los CSV de V08 por contenido, no por el nombre exacto.

    Esto evita depender de nombres como:
      participaciones(1).csv
      jugadores_consolidados(6).csv

    También permite que V08 genere:
      participaciones.csv
      jugadores_consolidados.csv
    """
    candidates = _csv_candidates()

    if kind == "participaciones":
        required = {
            "codigo", "jugador", "categoria", "competicion",
            "division", "jj", "mj", "jt", "g", "ag", "ta", "tr"
        }
        preferred = ("participaciones",)

    elif kind == "jugadores":
        required = {
            "codigo", "jugador", "id_liga_mx", "nui",
            "categoria", "categoria_registro", "posicion",
            "fecha_nacimiento", "edad", "url"
        }
        preferred = ("jugadores_consolidados",)

    else:
        raise ValueError(f"Tipo desconocido: {kind}")

    matches = []

    for path in candidates:
        try:
            cols = set(pd.read_csv(path, nrows=0).columns)
        except Exception:
            continue

        if required.issubset(cols):
            matches.append(path)

    if not matches:
        raise FileNotFoundError(
            f"No se encontró el CSV de {kind}.\n\n"
            f"CSV buscados dentro de:\n{BASE}\n\n"
            f"Archivos CSV encontrados:\n"
            + "\n".join(f"  - {p}" for p in candidates)
            + "\n\n"
            "Revisa que V08 haya generado sus resultados antes de ejecutar V09."
        )

    # Si hay varios candidatos válidos, preferimos el que tenga el
    # nombre esperado y, después, el más reciente.
    preferred_matches = [
        p for p in matches
        if any(token in p.stem.lower() for token in preferred)
    ]

    pool = preferred_matches or matches
    return max(pool, key=lambda p: p.stat().st_mtime)


PART_FILE = find_input_file("participaciones")
PLAYERS_FILE = find_input_file("jugadores")

print("=" * 60)
print("V09 — CONSOLIDACIÓN DE MINUTOS")
print("=" * 60)
print(f"Carpeta Pyto:    {BASE}")
print(f"Participaciones: {PART_FILE}")
print(f"Jugadores:       {PLAYERS_FILE}")
print(f"Salida V09:      {OUTPUT_DIR}")
print()

part = pd.read_csv(PART_FILE)
players = pd.read_csv(PLAYERS_FILE)

NUM_COLS = ["jj","mj","jt","g","ag","ta","tr"]
for c in NUM_COLS:
    part[c] = pd.to_numeric(part[c], errors="coerce").fillna(0).astype(int)

for c in ["categoria","division","competicion"]:
    part[c] = part[c].fillna("").astype(str).str.strip()

CAT_PRIORITY = {"Sub 21": 4, "Sub 19": 3, "Sub 17": 2, "Sub 15": 1}

MASTER_COLS = [
    "codigo","jugador","id_liga_mx","nui","categoria","categoria_registro",
    "posicion","fecha_nacimiento","edad","url"
]
master = players[MASTER_COLS].copy()

# -----------------------------
# 1. Consolidado por jugador
# -----------------------------
totals = part.groupby("codigo", as_index=False)[NUM_COLS].sum()
totals = totals.rename(columns={c: f"{c}_total" for c in NUM_COLS})

num_part = part.groupby("codigo").size().rename(
    "num_participaciones"
).reset_index()

div = part.groupby(["codigo","division"], as_index=False)["mj"].sum()
div_pivot = div.pivot(index="codigo", columns="division", values="mj").fillna(0).reset_index()
div_pivot.columns = [
    "codigo"
] + [
    f"mj_{str(c).lower().replace(' ','_')}"
    for c in div_pivot.columns[1:]
]

comp = part.groupby(["codigo","competicion"], as_index=False)["mj"].sum()
comp_pivot = comp.pivot(index="codigo", columns="competicion", values="mj").fillna(0).reset_index()
comp_pivot.columns = [
    "codigo"
] + [
    f"mj_{str(c).lower().replace(' ','_').replace('-','_')}"
    for c in comp_pivot.columns[1:]
]

outside = (
    part.assign(outside_category=part["division"] != part["categoria"])
    .groupby("codigo")
    .apply(
        lambda x: x.loc[x["outside_category"], "mj"].sum()
    )
    .rename("mj_fuera_categoria")
    .reset_index()
)

first_div = (
    part.groupby("codigo")
    .apply(
        lambda x: x.loc[x["division"].eq("Primera División"), "mj"].sum()
    )
    .rename("mj_primera_division")
    .reset_index()
)

# Preserve the V08.2 participation-state model:
# CON_MINUTOS / SIN_MINUTOS / SIN_PARTICIPACION
players_with_rows = set(part["codigo"])
positive = part.groupby("codigo")["mj"].sum()
state_map = {}
for code in master["codigo"]:
    if code not in players_with_rows:
        state_map[code] = "SIN_PARTICIPACION"
    elif int(positive.get(code, 0)) > 0:
        state_map[code] = "CON_MINUTOS"
    else:
        state_map[code] = "SIN_MINUTOS"

consolidated = master.merge(totals, on="codigo", how="left")
consolidated = consolidated.merge(num_part, on="codigo", how="left")
consolidated = consolidated.merge(div_pivot, on="codigo", how="left")
consolidated = consolidated.merge(comp_pivot, on="codigo", how="left")
consolidated = consolidated.merge(outside, on="codigo", how="left")
consolidated = consolidated.merge(first_div, on="codigo", how="left")

for c in consolidated.columns:
    if c.startswith(("jj_","mj_","jt_","g_","ag_","ta_","tr_","num_participaciones")):
        consolidated[c] = consolidated[c].fillna(0)

consolidated["mj_total"] = consolidated["mj_total"].fillna(0).astype(int)
consolidated["num_participaciones"] = consolidated["num_participaciones"].fillna(0).astype(int)
consolidated["mj_fuera_categoria"] = consolidated["mj_fuera_categoria"].fillna(0).astype(int)
consolidated["mj_primera_division"] = consolidated["mj_primera_division"].fillna(0).astype(int)

consolidated["mj_90s_equivalentes"] = (consolidated["mj_total"] / 90).round(2)

cat_max = consolidated.groupby("categoria")["mj_total"].transform("max")
club_max = int(consolidated["mj_total"].max())
consolidated["pct_mj_categoria"] = np.where(
    cat_max > 0,
    consolidated["mj_total"] / cat_max * 100,
    0
).round(2)
consolidated["pct_mj_club"] = np.where(
    club_max > 0,
    consolidated["mj_total"] / club_max * 100,
    0
).round(2)

divs_by_player = part.groupby("codigo")["division"].apply(set).to_dict()
consolidated["multicategoria_v09"] = consolidated.apply(
    lambda r: "SI" if any(d != r["categoria"] for d in divs_by_player.get(r["codigo"], set())) else "NO",
    axis=1
)
consolidated["estado_participacion_v09"] = consolidated["codigo"].map(state_map)

MAIN_COLS = MASTER_COLS + [
    "mj_total","jj_total","jt_total","g_total","ag_total","ta_total","tr_total",
    "num_participaciones","mj_fuera_categoria","mj_primera_division",
    "mj_90s_equivalentes","pct_mj_categoria","pct_mj_club",
    "multicategoria_v09","estado_participacion_v09"
]
main = consolidated[MAIN_COLS].sort_values(
    ["mj_total","jugador"], ascending=[False,True]
).reset_index(drop=True)

# -----------------------------
# 2. Minutos por división
# -----------------------------
div_out = (
    part.groupby(["codigo","jugador","categoria","division"], as_index=False)
    .agg(
        jj=("jj","sum"), mj=("mj","sum"), jt=("jt","sum"),
        g=("g","sum"), ag=("ag","sum"), ta=("ta","sum"), tr=("tr","sum"),
        num_competencias=("competicion","nunique")
    )
    .sort_values(["categoria","mj","jugador"], ascending=[True,False,True])
)

# -----------------------------
# 3. Minutos por competición
# -----------------------------
comp_out = (
    part.groupby(["codigo","jugador","categoria","competicion"], as_index=False)
    .agg(
        jj=("jj","sum"), mj=("mj","sum"), jt=("jt","sum"),
        g=("g","sum"), ag=("ag","sum"), ta=("ta","sum"), tr=("tr","sum"),
        num_divisiones=("division","nunique")
    )
    .sort_values(["competicion","mj","jugador"], ascending=[True,False,True])
)

# -----------------------------
# 4. Rankings por categoría
# -----------------------------
rank_base = main[
    ["codigo","jugador","categoria","mj_total",
     "pct_mj_categoria","pct_mj_club","estado_participacion_v09"]
].copy()

rank_cat_frames = []
for cat, df in rank_base.groupby("categoria", sort=True):
    d = df.sort_values(["mj_total","jugador"], ascending=[False,True]).copy()
    d["rango_categoria"] = d["mj_total"].rank(
        method="min", ascending=False
    ).astype(int)

    n = len(d)
    d["tipo"] = np.where(
        d["rango_categoria"] <= 5,
        "TOP 5",
        np.where(d["rango_categoria"] >= max(1, n - 4), "BOTTOM 5", "")
    )
    rank_cat_frames.append(d[d["tipo"] != ""])

rank_cat = pd.concat(rank_cat_frames, ignore_index=True)
rank_cat = rank_cat.sort_values(
    ["categoria","rango_categoria","mj_total","jugador"],
    ascending=[True,True,False,True]
)

# -----------------------------
# 5. Ranking global del club
# -----------------------------
# Approved tie rule:
# - MJ descending
# - if MJ tied across categories, category priority Sub21 > Sub19 > Sub17 > Sub15
# - same MJ + same category => same rank
rank_club = rank_base.copy()
rank_club["prioridad_categoria"] = rank_club["categoria"].map(
    CAT_PRIORITY
).fillna(0)

rank_club = rank_club.sort_values(
    ["mj_total","prioridad_categoria","jugador"],
    ascending=[False,False,True]
).reset_index(drop=True)

# Rank position advances only when MJ changes or category changes.
ranks = []
last_key = None
current_rank = 0
for _, row in rank_club.iterrows():
    key = (row["mj_total"], row["categoria"])
    if key != last_key:
        current_rank += 1
        last_key = key
    ranks.append(current_rank)

rank_club["rango"] = ranks
rank_club["tipo"] = np.where(
    rank_club["rango"] <= 10,
    "TOP 10",
    np.where(
        rank_club["rango"] >= max(rank_club["rango"]) - 9,
        "BOTTOM 10",
        ""
    )
)
rank_club = rank_club[rank_club["tipo"] != ""].sort_values(
    ["rango","mj_total","prioridad_categoria","jugador"],
    ascending=[True,False,False,True]
)

# -----------------------------
# 6. Resumen
# -----------------------------
summary = pd.DataFrame([{
    "jugadores": len(main),
    "participaciones": len(part),
    "mj_total_club": int(part["mj"].sum()),
    "jj_total_club": int(part["jj"].sum()),
    "jt_total_club": int(part["jt"].sum()),
    "g_total_club": int(part["g"].sum()),
    "ag_total_club": int(part["ag"].sum()),
    "ta_total_club": int(part["ta"].sum()),
    "tr_total_club": int(part["tr"].sum()),
    "max_mj_club": int(main["mj_total"].max()),
    "jugadores_con_minutos": int((main["mj_total"] > 0).sum()),
    "jugadores_sin_minutos": int((main["mj_total"] == 0).sum()),
    "sin_participacion": int((main["estado_participacion_v09"] == "SIN_PARTICIPACION").sum()),
    "sin_minutos": int((main["estado_participacion_v09"] == "SIN_MINUTOS").sum())
}])

# -----------------------------
# 7. Auditoría V09
# -----------------------------
participation_key = [
    "codigo","temporada","competicion","fase","division","club",
    "jj","mj","jt","g","ag","ta","tr"
]

player_mj = part.groupby("codigo")["mj"].sum()
main_mj = main.set_index("codigo")["mj_total"]
aligned = main_mj.subtract(player_mj.reindex(main_mj.index).fillna(0))

validation = {
    "players_v08": len(players),
    "players_v09": len(main),
    "participation_rows_v08": len(part),
    "mj_v08": int(part["mj"].sum()),
    "mj_v09": int(main["mj_total"].sum()),
    "player_mj_mismatches": int(aligned.ne(0).sum()),
    "exact_duplicate_participations": int(part.duplicated(subset=participation_key).sum()),
    "con_minutos": int((main["estado_participacion_v09"] == "CON_MINUTOS").sum()),
    "sin_minutos": int((main["estado_participacion_v09"] == "SIN_MINUTOS").sum()),
    "sin_participacion": int((main["estado_participacion_v09"] == "SIN_PARTICIPACION").sum()),
    "error": 0
}

# -----------------------------
# 8. Exportación
# -----------------------------
files = {
    "jugadores_consolidados_v09.csv": main,
    "minutos_por_division_v09.csv": div_out,
    "minutos_por_competicion_v09.csv": comp_out,
    "rankings_categoria_v09.csv": rank_cat,
    "ranking_club_v09.csv": rank_club,
    "resumen_v09.csv": summary,
    "auditoria_v09.csv": pd.DataFrame([validation])
}

for filename, df in files.items():
    df.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")

print("V09 ejecutado correctamente.")
print(validation)
for filename in files:
    print(OUTPUT_DIR / filename)

print()
print("V09 finalizado. Los archivos están en:")
print(OUTPUT_DIR)
