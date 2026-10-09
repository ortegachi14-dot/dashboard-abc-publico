from pathlib import Path
import csv, json, re, shutil, unicodedata
from datetime import datetime, date

BASE = Path(__file__).resolve().parent
MASTER = BASE / "Base_Maestra_ABC.csv"
V09 = BASE / "V09_resultados" / "jugadores_consolidados_v09.csv"
PARTICIPACIONES = BASE / "V08_copa_promesas" / "resultados" / "participaciones.csv"
OUT = BASE / "ABC"
HTML_FILE = OUT / "ABC_Ficha_Jugador_Oculto.html"
BACKUP = OUT / "ABC_backup_antes_actualizacion.html"
ASSETS = OUT / "assets" / "players"

OUT.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

def clean(v):
    s = "" if v is None else str(v).strip()
    return s if s else "Sin información"

def slug(v):
    s = unicodedata.normalize("NFKD", str(v or "").strip().lower())
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")

def contract_text(v):
    if v is None or not str(v).strip():
        return "Sin información"
    s = str(v).strip()
    try:
        obj = json.loads(s.replace("'", '"'))
        if isinstance(obj, list):
            return ", ".join(str(x).strip() for x in obj if str(x).strip()) or "Sin información"
        return clean(obj)
    except Exception:
        vals = [x.strip() for x in re.split(r"[,;|]", s.strip("[]").replace('"', "").replace("'", "")) if x.strip()]
        return ", ".join(vals) if vals else "Sin información"

def age_from_birth(v):
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(s[:10], fmt).date()
            t = date.today()
            return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
        except Exception:
            pass
    return ""

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

if not MASTER.exists():
    raise FileNotFoundError("No se encontró Base_Maestra_ABC.csv dentro de ~/Documents/Minutos FB/.")

if not V09.exists():
    raise FileNotFoundError("No se encontró V09_resultados/jugadores_consolidados_v09.csv.")
if not PARTICIPACIONES.exists():
    raise FileNotFoundError("No se encontró V08_copa_promesas/resultados/participaciones.csv; es necesario para mostrar los minutos por competencia y división en la ficha.")

master = read_csv(MASTER)
v09 = read_csv(V09)
participaciones = read_csv(PARTICIPACIONES)

def as_int(v):
    try: return int(float(v or 0))
    except Exception: return 0

def normalizar_division(v):
    s = clean(v)
    mapping = {"Fuerzas Básicas Sub 15":"Sub 15", "Fuerzas Básicas Sub 17":"Sub 17", "Fuerzas Básicas Sub 19":"Sub 19", "Fuerzas Básicas Sub 21":"Sub 21", "LIGA MX":"Primera División"}
    return mapping.get(s, s)

participaciones_por_codigo = {}
for row in participaciones:
    code = str(row.get("codigo", "")).strip()
    if not code: continue
    participaciones_por_codigo.setdefault(code, []).append({
        "competicion": clean(row.get("competicion")),
        "temporada": clean(row.get("temporada")),
        "fase": clean(row.get("fase")),
        "division": normalizar_division(row.get("division")),
        "jj": as_int(row.get("jj")), "mj": as_int(row.get("mj")),
        "jt": as_int(row.get("jt")), "g": as_int(row.get("g")),
        "ag": as_int(row.get("ag")), "ta": as_int(row.get("ta")), "tr": as_int(row.get("tr"))
    })

required = {"Jugador","Código de jugador","Categoría","Clase","Contrato","Posición","Fecha de nacimiento","Edad","URL"}
missing = required - set(master[0].keys()) if master else required
casa_col = next((c for c in (master[0].keys() if master else []) if c.strip().lower() == "casa club"), None)
if not casa_col:
    raise ValueError("Falta la columna Casa Club en Base_Maestra_ABC.csv.")
if missing:
    raise ValueError("Faltan columnas en Base_Maestra_ABC.csv: " + ", ".join(sorted(missing)))

minutes = {}
for r in v09:
    code = str(r.get("codigo","")).strip()
    try:
        minutes[code] = int(float(r.get("mj_total",0) or 0))
    except Exception:
        minutes[code] = 0

# Copiar fotos existentes en Minutos FB hacia ABC/assets/players.
photo_sources = {}
for p in BASE.rglob("*"):
    if p.is_file() and p.suffix.lower() in {".png",".jpg",".jpeg",".webp"} and ASSETS not in p.parents:
        photo_sources[slug(p.stem)] = p

for p in photo_sources.values():
    target = ASSETS / p.name
    if not target.exists():
        shutil.copy2(p, target)

photo_map = {slug(p.stem):p.name for p in ASSETS.iterdir() if p.is_file() and p.suffix.lower() in {".png",".jpg",".jpeg",".webp"}}

def find_photo(name):
    key = slug(name)
    if key in photo_map:
        return "assets/players/" + photo_map[key]
    for k, fn in photo_map.items():
        if k.startswith(key) or key.startswith(k):
            return "assets/players/" + fn
    return ""

players = []
for r in master:
    birth = clean(r.get("Fecha de nacimiento"))
    age = age_from_birth(birth)
    if not age:
        m = re.search(r"\d+", clean(r.get("Edad")))
        age = int(m.group()) if m else ""
    cls = clean(r.get("Clase")).upper()
    if cls not in {"A","B","C"}:
        cls = "Sin información"
    code = clean(r.get("Código de jugador"))
    name = clean(r.get("Jugador"))
    players.append({
        "codigo":code,
        "jugador":name,
        "categoria":clean(r.get("Categoría")),
        "clase":cls,
        "contrato":contract_text(r.get("Contrato")),
        "posicion":clean(r.get("Posición")),
        "edad":f"{age} años" if age else "Sin información",
        "fechaNacimiento":birth,
        "minutos":minutes.get(code,0),
        "participaciones":participaciones_por_codigo.get(code, []),
        "url":clean(r.get("URL")),
        "foto":find_photo(name),
        "casaClub":clean(r.get(casa_col)).strip().lower() in {"si","sí","yes","true","1"}
    })

DATA = json.dumps(players, ensure_ascii=False, separators=(",",":"))

HTML = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Club Tijuana - ABC</title>
<style>
body{margin:0;background:linear-gradient(180deg,rgba(0,0,0,.50),rgba(0,0,0,.94) 78%),linear-gradient(90deg,rgba(200,16,46,.20),transparent 45%,rgba(200,16,46,.08)),url("https://upload.wikimedia.org/wikipedia/commons/7/7c/Estadio_Caliente.JPG") center top/cover fixed no-repeat;color:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.header{background:rgba(5,5,5,.82);border-bottom:1px solid #292929;padding:15px 24px;backdrop-filter:blur(10px)}.brand{max-width:1450px;margin:auto;display:flex;align-items:center;gap:14px}.club-logo{width:52px;height:52px;object-fit:contain;filter:drop-shadow(0 5px 14px rgba(0,0,0,.6))}.eyebrow{color:#888;font-size:10px;letter-spacing:2px;text-transform:uppercase}h1{margin:3px 0;font-size:23px}
.wrap{max-width:1450px;margin:auto;padding:25px 24px 60px}.hero{min-height:calc(100vh - 110px);display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}.hero h2{font-size:40px;margin:7px 0}.hero.selected{min-height:auto;padding:35px 0 15px}.hero.selected p{margin-bottom:4px}.hero p{max-width:650px;color:#999;line-height:1.6}.redline{width:65px;height:3px;background:#c8102e;margin:20px auto}.cover-filters{margin-top:24px;width:min(850px,100%);padding:18px 20px;border:1px solid rgba(255,255,255,.10);border-radius:14px;background:rgba(8,8,8,.68);backdrop-filter:blur(10px)}.filter-label{color:#888;font-size:10px;letter-spacing:2px;text-transform:uppercase;text-align:left;margin:3px 0 8px}.cover-filters .tabs{justify-content:center;margin-bottom:14px}.cover-filters button{min-width:92px}.cover-filters button.active{box-shadow:0 0 0 1px rgba(255,255,255,.18),0 5px 18px rgba(200,16,46,.20)}{width:65px;height:3px;background:#c8102e;margin-top:20px}
.selection{display:none}.selection.visible{display:block}.toolbar{display:flex;gap:10px;margin-bottom:18px}.search{flex:1;padding:13px 15px;border-radius:8px;border:1px solid #383838;background:#101010;color:#fff;font-size:15px}.count{padding:13px 16px;border:1px solid #303030;border-radius:8px;background:#111}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 22px}button{border:1px solid #383838;background:#111;color:#ddd;padding:10px 17px;border-radius:7px;cursor:pointer;font-weight:800}button.active{background:#c8102e;border-color:#c8102e;color:#fff}button.ca.active{background:#23864a;border-color:#23864a}button.cb.active{background:#b88a18;border-color:#b88a18}button.cc.active{background:#9d3030;border-color:#9d3030}button.casa.active{background:#c8102e;border-color:#c8102e}.tab-separator{width:1px;height:28px;background:#444;display:inline-block;margin:0 4px;align-self:center}
.section-head{display:flex;justify-content:space-between;border-bottom:1px solid #333;padding-bottom:10px;margin-bottom:10px}.section-head h2{margin:0;font-size:18px}.order{color:#888;font-size:12px}
.table-wrap{overflow-x:auto;border:1px solid #292929;border-radius:10px;background:#0a0a0a}table{width:100%;min-width:1050px;border-collapse:collapse}thead{background:#151515}th{text-align:left;color:#888;font-size:10px;letter-spacing:1px;text-transform:uppercase;padding:12px 13px;border-bottom:1px solid #333}td{padding:9px 13px;border-bottom:1px solid #252525;font-size:13px}.player{display:flex;align-items:center;gap:11px;min-width:270px}.photo{width:43px;height:55px;object-fit:cover;border-radius:5px;background:#252525}.no-photo{display:flex;align-items:center;justify-content:center;color:#777;font-size:8px}.player-name{font-weight:800}.sub{color:#777;font-size:10px;margin-top:3px}.badge{display:inline-block;min-width:28px;text-align:center;padding:5px 8px;border-radius:5px;color:#fff;font-weight:900;font-size:11px}.badge.A{background:#23864a}.badge.B{background:#b88a18}.badge.C{background:#9d3030}.badge.none{background:#333;color:#aaa}.minutes{font-size:17px;font-weight:900}.empty{padding:45px;text-align:center;color:#888}.note{color:#777;font-size:11px;margin-top:14px}.click-hint{color:#777;font-size:10px;margin-top:4px}.player-select-button{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:11px;width:100%;min-width:270px;padding:6px;border:1px solid transparent;border-radius:9px;cursor:pointer;transition:background .16s ease,border-color .16s ease,box-shadow .16s ease}.player-select-button:hover,.player-select-button:focus-visible{background:transparent;border-color:transparent;box-shadow:none;outline:none}.player-row{cursor:pointer}.player-row:hover td,.player-row:focus-visible td{background:rgba(200,16,46,.085);border-top:1px solid rgba(200,16,46,.50);border-bottom:1px solid rgba(200,16,46,.50)}.player-row:hover td:first-child,.player-row:focus-visible td:first-child{border-left:1px solid rgba(200,16,46,.60);border-top-left-radius:9px;border-bottom-left-radius:9px}.player-row:hover td:last-child,.player-row:focus-visible td:last-child{border-right:1px solid rgba(200,16,46,.60);border-top-right-radius:9px;border-bottom-right-radius:9px}.player-row:focus-visible{outline:none}.player-row:hover .player-name,.player-row:focus-visible .player-name{color:#fff}.contract-red{color:#ff5268!important}.contract-yellow{color:#f1c84b!important}.contract-white{color:#f5f5f5!important}.contract-reveal{display:inline-block;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;filter:blur(5px);opacity:.55;transition:filter .15s ease,opacity .15s ease;cursor:pointer;user-select:none;border:1px solid #343434;border-radius:5px;padding:5px 8px;background:#141414}.contract-reveal:hover,.contract-reveal:focus-visible,.contract-reveal.revealed{filter:none;opacity:1}.contract-reveal:focus-visible{outline:1px solid #c8102e;outline-offset:2px}.contract-cell{white-space:nowrap}.contract-hint{display:block;color:#666;font-size:9px;margin-top:3px}.contract-profile{display:inline-block;text-align:left;max-width:100%;filter:blur(5px);opacity:.55;cursor:pointer;transition:filter .15s ease,opacity .15s ease}.contract-profile:hover,.contract-profile:focus-visible,.contract-profile.revealed{filter:none;opacity:1}.contract-profile button{font-size:12px;padding:5px 8px}. casa-club-yes{color:#7de6a2!important}.personal-item.class-A{background:rgba(35,134,74,.28);border:1px solid rgba(55,190,105,.55)}.personal-item.class-B{background:rgba(184,138,24,.24);border:1px solid rgba(241,200,75,.55)}.personal-item.class-C{background:rgba(157,48,48,.28);border:1px solid rgba(235,72,84,.55)}.personal-item.class-A b{color:#7de6a2}.personal-item.class-B b{color:#ffe17a}.personal-item.class-C b{color:#ff858e}.modal{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.78);backdrop-filter:blur(7px);display:none;align-items:center;justify-content:center;padding:18px}.modal.open{display:flex}.modal-card{position:relative;width:min(900px,100%);max-height:92vh;overflow:auto;background:#0e0f12;border:1px solid #303035;border-radius:20px;box-shadow:0 24px 80px #000;padding:22px}.modal-close{position:absolute;right:14px;top:12px;border-radius:50%;width:38px;height:38px;padding:0;font-size:20px}.profile-head{display:grid;grid-template-columns:180px 1fr;gap:22px;align-items:start;padding:6px 28px 20px 0}.profile-photo{width:100%;height:230px;object-fit:cover;border-radius:12px;background:#222}.profile-category{font-size:11px;color:#ff304b;font-weight:900;letter-spacing:2px;text-transform:uppercase}.profile-name{font-size:clamp(22px,4vw,32px);margin:6px 0 10px}.profile-minutes{font-size:48px;font-weight:900;line-height:1.05}.muted{color:#999;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;margin-top:7px}.profile-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:16px}.stat{padding:12px;border:1px solid #303035;background:#17181c;border-radius:12px}.stat b{font-size:20px;display:block}.stat span{font-size:9px;color:#999;text-transform:uppercase;letter-spacing:.6px}.modal-section{border-top:1px solid #303035;padding-top:16px;margin-top:12px}.modal-section h3{font-size:12px;letter-spacing:1.4px;margin:0 0 12px}.where-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.where-card{border:1px solid #4b1822;background:#1b1014;border-radius:12px;padding:12px}.where-card b{font-size:23px;display:block}.where-card span{color:#aaa;font-size:10px}.personal-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.personal-item{background:#17181c;border-radius:9px;padding:11px;min-width:0}.personal-item span{display:block;color:#999;font-size:9px;text-transform:uppercase;letter-spacing:.7px;margin-bottom:5px}.personal-item b{font-size:13px;overflow-wrap:anywhere}.participation-list{display:grid;gap:8px}.participation-row{display:flex;justify-content:space-between;gap:15px;align-items:center;background:#17181c;border-radius:10px;padding:12px}.participation-row b{display:block;font-size:14px}.participation-row small{color:#999;font-size:11px}.participation-minutes{font-size:17px;font-weight:900;white-space:nowrap}.profile-link{display:inline-block;color:#ff5268;margin-top:10px;font-size:12px}@media(max-width:600px){.modal{padding:8px}.modal-card{padding:15px;border-radius:14px}.profile-head{grid-template-columns:100px 1fr;gap:13px;padding-right:25px}.profile-photo{height:135px}.profile-minutes{font-size:34px}.profile-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.where-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.personal-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.participation-row{padding:10px}.participation-row b{font-size:12px}}
</style></head><body>
<header class="header"><div class="brand"><img class="club-logo" src="https://www.footylogos.com/downloads/logo/club-tijuana-logo-footylogos.png" alt="Club Tijuana"><div><div class="eyebrow">Club Tijuana Xoloitzcuintles</div><h1>Desarrollo Individual · Clasificación de Jugadores</h1></div></div></header>
<main class="wrap">
<section id="hero" class="hero">
<div class="eyebrow">Desarrollo Individual</div>
<h2>Minutos por Clasificación A / B / C</h2>
<p>Selecciona una categoría o una clase para consultar a los jugadores.</p>
<div class="redline"></div>
<div class="cover-filters">
<div class="filter-label">CATEGORÍA</div><div class="tabs" id="coverCategoryTabs"></div>
<div class="filter-label">CLASE</div><div class="tabs" id="coverClassTabs"></div>
</div>
</section>
<section id="selection" class="selection"><div class="toolbar"><input id="search" class="search" placeholder="Buscar jugador..."><div id="resultCount" class="count">0 jugadores</div></div>
<div id="content"></div></section>
<div id="playerModal" class="modal" onclick="if(event.target===this)closePlayer()"><div class="modal-card"><button class="modal-close" onclick="closePlayer()" aria-label="Cerrar">×</button><div id="playerProfile"></div></div></div>
</main>
<script>
const PLAYERS=__DATA__;
let selectedCategory=null,selectedClass=null,casaClub=false,search="";
const CATEGORIES=["Sub 21","Sub 19","Sub 17","Sub 15"],CLASSES=["A","B","C"];
function esc(v){return String(v).replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}
function show(){document.getElementById("selection").classList.add("visible");document.getElementById("hero").classList.add("selected")}
function selectCategory(v){show();casaClub=false;selectedCategory=selectedCategory===v?null:v;selectedClass=null;render()}
function selectClass(v){show();selectedClass=selectedClass===v?null:v;render()}
function selectCasaClub(){show();casaClub=!casaClub;if(casaClub){selectedCategory=null}render()}
function toggleContract(el){el.classList.toggle("revealed")}
function contractClass(value){
 const text=String(value||"");
 const matches=[...text.matchAll(/\\b(?:AP|CL)\\s*[-/]?\\s*(\\d{2}|20\\d{2})\\b/gi)];
 if(!matches.length)return "contract-white";
 const years=matches.map(m=>{const n=Number(m[1]);return n<100?2000+n:n;});
 const yearsAway=Math.min(...years)-new Date().getFullYear();
 if(yearsAway<=1)return "contract-red";
 if(yearsAway===2)return "contract-yellow";
 return "contract-white";
}
function renderTabs(){
let x='<button class="'+(selectedCategory===null?"active":"")+'" onclick="selectCategory(null)">TODAS</button>';
CATEGORIES.forEach(v=>x+='<button class="'+(selectedCategory===v&&!casaClub?"active":"")+'" data-value="'+v+'" onclick="selectCategory(this.dataset.value)">'+v+'</button>');
x+='<span class="tab-separator"></span><button class="casa '+(casaClub?"active":"")+'" onclick="selectCasaClub()">CASA CLUB</button>';
document.getElementById("coverCategoryTabs").innerHTML=x;
let y='<button class="'+(selectedClass===null?"active":"")+'" onclick="selectClass(null)">TODAS</button>';
CLASSES.forEach(v=>{let c=v==="A"?"ca":v==="B"?"cb":"cc";y+='<button class="'+c+" "+(selectedClass===v?"active":"")+'" data-value="'+v+'" onclick="selectClass(this.dataset.value)">CLASE '+v+'</button>'});
document.getElementById("coverClassTabs").innerHTML=y}
function table(arr){
if(!arr.length)return '<div class="empty">No hay jugadores que coincidan con los filtros seleccionados.</div>';
return '<div class="table-wrap"><table><thead><tr><th>Jugador</th><th>Clase</th><th>Minutos</th><th>Categoría</th><th>Edad</th><th>Fecha de nacimiento</th><th>Posición</th><th>Contrato</th></tr></thead><tbody>'+arr.map(p=>{
let photo=p.foto?'<img class="photo" src="'+p.foto+'" loading="lazy">':'<div class="photo no-photo">Sin foto</div>';
let bc=["A","B","C"].includes(p.clase)?p.clase:"none";
return '<tr class="player-row" data-code="'+esc(p.codigo)+'" tabindex="0" role="button" aria-label="Abrir ficha de '+esc(p.jugador)+'" onclick="openPlayer(this.dataset.code)" onkeydown="if(event.keyCode===13||event.keyCode===32){event.preventDefault();openPlayer(this.dataset.code)}"><td><button type="button" class="player-select-button" data-code="'+esc(p.codigo)+'" onclick="event.stopPropagation();openPlayer(this.dataset.code)" aria-label="Abrir ficha de '+esc(p.jugador)+'">'+photo+'<div><div class="player-name">'+esc(p.jugador)+'</div><div class="click-hint">Ver ficha ↗</div></div></button></td><td><span class="badge '+bc+'">'+esc(p.clase)+'</span></td><td><span class="minutes">'+Number(p.minutos||0).toLocaleString("es-MX")+'</span></td><td>'+esc(p.categoria)+'</td><td>'+esc(p.edad)+'</td><td>'+esc(p.fechaNacimiento)+'</td><td>'+esc(p.posicion)+'</td><td class="contract-cell" onclick="event.stopPropagation()"><span class="contract-reveal '+contractClass(p.contrato)+'" tabindex="0" role="button" aria-label="Revelar contrato" title="Pasa el cursor o toca para revelar" onclick="event.stopPropagation();toggleContract(this)" onkeydown="if(event.keyCode===13||event.keyCode===32){event.preventDefault();event.stopPropagation();toggleContract(this)}">'+esc(p.contrato)+'</span><small class="contract-hint">Pasar / tocar</small></td></tr>'}).join("")+'</tbody></table></div>'}
function normalizeText(value){return String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase()}
function render(){
renderTabs();
let arr=PLAYERS.filter(p=>(casaClub?(p.casaClub&&(selectedClass===null||p.clase===selectedClass)):(selectedCategory===null||p.categoria===selectedCategory)&&(selectedClass===null||p.clase===selectedClass))&&normalizeText(p.jugador).includes(normalizeText(search).trim()));
arr.sort((a,b)=>(Number(b.minutos)||0)-(Number(a.minutos)||0)||a.jugador.localeCompare(b.jugador,"es"));
document.getElementById("resultCount").innerHTML="<b>"+arr.length+"</b> jugadores";
let title=casaClub?(selectedClass?"CASA CLUB · CLASE "+selectedClass:"CASA CLUB"):selectedCategory&&selectedClass?selectedCategory+" · CLASE "+selectedClass:selectedCategory||(selectedClass?"CLASE "+selectedClass:"TODOS LOS JUGADORES");
document.getElementById("content").innerHTML='<div class="section-head"><h2>'+title+'</h2><div class="order">Orden: minutos jugados ↓</div></div>'+table(arr)+'<div class="note">Clase y contrato: Base Maestra ABC · Minutos: V09</div>'}
function openPlayer(code){
 const p=PLAYERS.find(x=>x.codigo===code);if(!p)return;
 const parts=(p.participaciones||[]).slice().sort((a,b)=>b.mj-a.mj||a.competicion.localeCompare(b.competicion,"es"));
 const byDivision={};parts.forEach(x=>{const k=x.division; if(!byDivision[k])byDivision[k]={mj:0,jj:0,jt:0};byDivision[k].mj+=x.mj;byDivision[k].jj+=x.jj;byDivision[k].jt+=x.jt});
 const where=Object.entries(byDivision).sort((a,b)=>b[1].mj-a[1].mj).map(([d,x])=>'<div class="where-card"><b>'+x.mj.toLocaleString("es-MX")+'′</b><span>'+esc(d)+' · '+x.jj+' JJ · '+x.jt+' JT</span></div>').join("")||'<div class="empty">Sin participaciones registradas.</div>';
 const rows=parts.map(x=>'<div class="participation-row"><div><b>'+esc(x.competicion)+'</b><small>'+esc(x.division)+' · '+esc(x.temporada)+(x.fase&&x.fase!=="Sin información"?' · '+esc(x.fase):'')+' · '+x.jj+' JJ · '+x.jt+' JT · '+x.g+' G</small></div><div class="participation-minutes">'+x.mj.toLocaleString("es-MX")+'′</div></div>').join("")||'<div class="empty">Sin participaciones registradas.</div>';
 const photo=p.foto?'<img class="profile-photo" src="'+p.foto+'">':'<div class="profile-photo"></div>';
 const personal=[['Clase',p.clase],['Categoría',p.categoria],['Edad',p.edad],['Fecha de nacimiento',p.fechaNacimiento],['Posición',p.posicion],['Contrato',p.contrato],['Casa Club',p.casaClub?'Sí':'No']];
 const info=personal.map(([k,v])=>{const cls=k==='Clase'&&['A','B','C'].includes(String(v))?' class-'+v:'';const contract=k==='Contrato'?' '+contractClass(v):'';const casa=k==='Casa Club'&&String(v).toLowerCase()==='sí'?' casa-club-yes':'';if(k==='Contrato')return '<div class="personal-item'+cls+'"><span>'+esc(k)+'</span><b class="contract-profile '+contract.trim()+'" tabindex="0" role="button" onclick="event.stopPropagation();toggleContract(this)" onkeydown="if(event.keyCode===13||event.keyCode===32){event.preventDefault();toggleContract(this)}" title="Pasa el cursor o toca para revelar">'+esc(v||'Sin información')+'</b><small class="contract-hint">Pasar / tocar</small></div>';return '<div class="personal-item'+cls+'"><span>'+esc(k)+'</span><b class="'+(contract.trim()+casa).trim()+'">'+esc(v||'Sin información')+'</b></div>'}).join('');
 document.getElementById('playerProfile').innerHTML='<div class="profile-head">'+photo+'<div><div class="profile-category">'+esc(p.categoria)+' · CLASE '+esc(p.clase)+'</div><h2 class="profile-name">'+esc(p.jugador)+'</h2><div class="profile-minutes">'+Number(p.minutos||0).toLocaleString("es-MX")+'′</div><div class="muted">Minutos totales</div><div class="profile-stats"><div class="stat"><b>'+parts.reduce((s,x)=>s+x.jj,0)+'</b><span>JJ acumulados</span></div><div class="stat"><b>'+parts.reduce((s,x)=>s+x.jt,0)+'</b><span>JT acumulados</span></div><div class="stat"><b>'+parts.reduce((s,x)=>s+x.g,0)+'</b><span>Goles</span></div></div></div></div><div class="modal-section"><h3>INFORMACIÓN DEL JUGADOR</h3><div class="personal-grid">'+info+'</div>'+'</div><div class="modal-section"><h3>DÓNDE JUGÓ LOS MINUTOS</h3><div class="where-grid">'+where+'</div></div><div class="modal-section"><h3>MINUTOS POR COMPETENCIA Y DIVISIÓN</h3><div class="participation-list">'+rows+'</div></div>';
 document.getElementById('playerModal').classList.add('open');document.body.style.overflow='hidden';
}
function closePlayer(){document.getElementById('playerModal').classList.remove('open');document.body.style.overflow=''}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePlayer()});
document.getElementById("search").addEventListener("input",e=>{search=e.target.value;render()});renderTabs();
</script></body></html>"""

HTML = HTML.replace("__DATA__", DATA)

if HTML_FILE.exists():
    shutil.copy2(HTML_FILE, BACKUP)

HTML_FILE.write_text(HTML, encoding="utf-8")

a=sum(p["clase"]=="A" for p in players)
b=sum(p["clase"]=="B" for p in players)
c=sum(p["clase"]=="C" for p in players)
photos=sum(bool(p["foto"]) for p in players)

print("==============================================")
print("CLUB TIJUANA — DASHBOARD ABC")
print("==============================================")
print("Fuente jugadores:", MASTER)
print("Fuente minutos:", V09)
print("Jugadores:", len(players))
print("Clase A:", a, "| Clase B:", b, "| Clase C:", c)
print("Fotos encontradas:", photos)
print("Salida:", HTML_FILE)
print("==============================================")
