"""Importador conservador. Por defecto NO escribe; --aplicar inserta solo coincidencias verificables.
Ejecutar en el entorno con DATABASE_URL configurada. Nunca compartir la URL.
"""
import argparse, ast, csv, hashlib, json, re, unicodedata
from pathlib import Path
from collections import Counter
from datetime import date
from lector_excel_ptap import parse_excel, exceldate, clock, norm
from database import SessionLocal, engine, Base
import models

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'fuente_noviembre_2026.xlsx'
parser=argparse.ArgumentParser();parser.add_argument('--aplicar',action='store_true');args=parser.parse_args()

# Leer la matriz oficial sin iniciar el servidor.
tree=ast.parse((HERE/'main.py').read_text(encoding='utf-8'))
master=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAESTRA_PLAN_CALIDAD' for t in n.targets))
index={(norm(z),norm(p)):(z,p,lim) for z,p,_,_,_,lim,_ in master}

def parsefloat(v):
    try:return float(str(v).replace(',','.')) if v not in (None,'') else None
    except (ValueError,TypeError):return None

def state(value,spec):
    t=str(value).strip().lower()
    if t in ('na','n.a','n.a.','no aplica'):return 'No aplica'
    if t in ('fs','fuera de servicio'):return 'Pendiente'
    if t in ('pasa','cumple'):return 'Cumple'
    if t in ('no pasa','no cumple'):return 'FUERA DE RANGO'
    n=parsefloat(value)
    if n is None:return 'Pendiente'
    s=str(spec).replace(',','.').lower().replace('ppm','').replace('ntu','').replace('psi','').strip()
    # No inferir cumplimiento sin límite numérico explícito.
    bounds=re.findall(r'[-+]?\d+(?:\.\d+)?',s)
    if '≥' in s or '>=' in s:return 'Cumple' if bounds and n>=float(bounds[0]) else 'FUERA DE RANGO'
    if '<' in s:return 'Cumple' if bounds and n<float(bounds[0]) else 'FUERA DE RANGO'
    if '>' in s:return 'Cumple' if bounds and n>float(bounds[0]) else 'FUERA DE RANGO'
    if len(bounds)>=2 and (' a ' in s or '-' in s):return 'Cumple' if float(bounds[0])<=n<=float(bounds[1]) else 'FUERA DE RANGO'
    return 'Pendiente'

# Correcciones explícitas y trazables de nombres Excel a matriz.
def map_plan(zone,param,sample):
    z,p=norm(zone),norm(param)
    if p in ('pozo1','pozo2','pozo3','rio') and ('aguafuente' in z or not z):
        name='Agua Fuente (Río)' if p=='rio' else 'Agua Fuente (Pozo '+p[-1]+')'
        return index.get((norm('Entrada Agua Potable'),norm(name)))
    if p in ('carbonoorganicototal','cot'):
        if z in ('pozo1','pozo2','pozo3','rio'):
            name='COT ('+('Rio' if z=='rio' else 'Pozo '+z[-1])+')'
            return index.get((norm('Entrada Agua Potable'),norm(name)))
        if z==norm('Entrada Agua Potable'):p=norm('COT (Entrada agua potable)')
        else:p=norm('COT')
    if p=='clororesidual' and z==norm('Entrada Agua Potable'):
        p=norm('Cloro residual (Muestra '+str(sample)+')')
    if p=='ph' and 'tratamientoconluzultravioleta' in z:
        p=norm('pH (Muestra '+str(sample)+')')
    if p=='evaluacionsensorialolorysabor':p=norm('Evaluación Sensorial')
    if p=='turbiedadlaboratorio':p=norm('Turbiedad (Lab)')
    if p=='turbiedadlinea':p=norm('Turbiedad (Linea)')
    if p=='clororesidualfc1':p=norm('Cloro residual F C1')
    if p=='clororesidualfc2':p=norm('Cloro residual F C2')
    if p=='clororesidualfc3':p=norm('Cloro residual F C3')
    if p=='clororesiduallaboratorio':p=norm('Cloro residual (Lab)')
    if p=='concentraciondioxidodeclorolaboratorio':p=norm('Concentración dioxido de cloro (Lab)')
    if p=='concentraciondioxidodeclorolinea':p=norm('Concentración dioxido de cloro (Linea)')
    if p=='dioxidodeclorosalidatkawt':p=norm('Dióxido de Cloro')
    if 'ultrafiltracion' in z and 'cervecera' in z:
        z=z.replace('cervecera','cervezera')
    if z==norm('Tanque de almacenamiento PTAP Servicios'):z=norm('Tanque de almacenamiento PATP Servicios')
    if z==norm('Filtración por carbón agua  de Servicios'):z=norm('Filtracion por carbon agua de servicios')
    if z==norm('Filtración por carbón agua cervecera'):z=norm('Filtracion por carbon agua cervecera')
    if z==norm('Salida tren filtros agua de servicios'):z=norm('Salida tren filtros agua de servicios')
    return index.get((z,p))

def record_key(sheet,row,day,slot):return hashlib.sha256(f'nov2026|{sheet}|{row}|{day}|{slot}'.encode()).hexdigest()

sheets={name:dict(rows) for name,rows in parse_excel(SOURCE)}
results=[]
def submit(module,key,obj,identity,details):results.append((module,key,obj,identity,details))

# PLAN DE CALIDAD: cada columna corresponde a medición individual y a un turno.
d=sheets['Plan Calidad'];last_zone=''
for rn in range(4,111):
    c=d.get(rn,{})
    if c.get(2):last_zone=str(c[2]).strip()
    par=str(c.get(3,'')).strip()
    if not par:continue
    for start in range(6,36,6):
        day=exceldate(d[1].get(start))
        if not day or not day.startswith('2026-11-'):continue
        for slot in range(6):
            value=c.get(start+slot)
            if value is None:continue
            turno=f'Turno {slot//2+1}';sample=slot%2+1
            match=map_plan(last_zone,par,sample)
            op=d.get(3,{}).get(start+(slot//2)*2,'')
            key=record_key('Plan Calidad',rn,day,slot)
            if not match:
                submit('Plan de Calidad',key,None,None,f'Sin correspondencia: fila {rn} {last_zone} / {par}')
                continue
            z,p,lim=match
            # No declarar un análisis no programado como conforme automáticamente.
            obj=models.RegistroPlanCalidad(fecha=day,turno=turno,operador=str(op).strip(),zona=z,parametro=p,
                                          valor=str(value),resultado=state(value,c.get(4,'')),limite=str(c.get(4,'') or lim))
            identity=(day,turno,z,p)
            submit('Plan de Calidad',key,obj,identity,f'Fila {rn}; muestra {sample}; {par}')

# FILTROS
for rn,c in sheets['LimpiezaFiltrosCarbón'].items():
    if rn<=5 or not c.get(1) or not c.get(2):continue
    day=exceldate(c[1]);typ=str(c.get(5,'')).strip().upper();equip=str(c.get(2,'')).strip()
    if not day or not day.startswith('2026-11-'):continue
    key=record_key('LimpiezaFiltrosCarbón',rn,day,0)
    if typ not in ('RP','E'):
        submit('Filtros',key,None,None,f'Fila {rn}: tipo no reconocido {typ}')
        continue
    ini=clock(c.get(7));fin=clock(c.get(8))
    agua_ini=parsefloat(c.get(11));agua_fin=parsefloat(c.get(12))
    obj=models.RegistroLimpiezaFiltro(fecha=day,equipo=equip,operador=str(c.get(4,'')).strip(),
       tipo_limpieza=typ,hora_muestra_antes=clock(c.get(6)),hora_inicio_est=ini,hora_final_est=fin,
       hora_muestra_despues=clock(c.get(9)),temperatura=str(c.get(10,'') or ''),
       perdida_carbon=str(c.get(16,'No')),agua_inicial=agua_ini,agua_final=agua_fin,
       consumo_agua=round(agua_fin-agua_ini,2) if agua_ini is not None and agua_fin is not None and agua_fin>=agua_ini else None,
       cloro=str(c.get(14,'') or ''),turbidez=str(c.get(15,'') or ''))
    submit('Filtros',key,obj,(day,equip,typ,ini,fin),f'Fila {rn}')

# UF: se conservan campos vacíos como vacíos, sin inventar concentraciones.
for rn,c in sheets['Limpieza  UF'].items():
    if rn<=5 or not c.get(1) or not c.get(2):continue
    day=exceldate(c[1]);eq=str(c[2]).strip()
    if not day or not day.startswith('2026-11-'):continue
    key=record_key('Limpieza  UF',rn,day,0)
    if norm(eq)=='f211':
        submit('Limpieza UF',key,None,None,f'Fila {rn}: equipo F211 ambiguo; requiere confirmación')
        continue
    ini=clock(c.get(5));fin=clock(c.get(6));ai=parsefloat(c.get(9));af=parsefloat(c.get(10))
    obj=models.RegistroLimpiezaUF(fecha=day,equipo=eq,operador=str(c.get(3,'')),tipo_limpieza=str(c.get(4,'')),
        hora_inicio=ini,hora_final=fin,concentracion_1=str(c.get(7,'') or ''),concentracion_2=str(c.get(8,'') or ''),
        agua_inicial=ai,agua_final=af,consumo_agua=round(af-ai,2) if ai is not None and af is not None and af>=ai else None,
        turbiedad=str(c.get(12,'') or ''),ph_final=str(c.get(13,'') or ''),observaciones=str(c.get(14,'') or ''))
    submit('Limpieza UF',key,obj,(day,norm(eq),norm(c.get(4,'')),ini,fin),f'Fila {rn}')

# CONTADORES: una fila por fecha; NO importar fechas de septiembre dentro de noviembre.
d=sheets['Control Contadores 24h'];hdr=d[1];sub=d[2]
for rn,c in d.items():
    if rn<=2 or not c.get(1):continue
    day=exceldate(c[1]);key=record_key('Control Contadores 24h',rn,day,0)
    if not day or not day.startswith('2026-11-'):
        if rn<=7:submit('Contadores 24h',key,None,None,f'Fila {rn}: fecha {day} fuera de noviembre; requiere corrección')
        continue
    lect={}
    for col,v in sorted(c.items()):
        if col==1 or v is None or 'total' in norm(sub.get(col,'')):continue
        if 'lectura' not in norm(sub.get(col,'')):continue
        name=''
        for k in sorted(hdr):
            if k<=col:name=str(hdr[k]).strip()
        if name:lect[name]=parsefloat(v) if parsefloat(v) is not None else str(v)
    obj=models.RegistroContador24h(fecha=day,operador='',lecturas_json=json.dumps(lect,ensure_ascii=False))
    submit('Contadores 24h',key,obj,day,f'Fila {rn}; {len(lect)} lecturas')

if args.aplicar:
    Base.metadata.create_all(bind=engine)
counts=Counter();issues=[]
with SessionLocal() as db:
    for mod,key,obj,identity,detail in results:
        if obj is None:counts[(mod,'REVISAR')]+=1;issues.append((mod,detail));continue
        if db.query(models.RegistroImportacionOrigen).filter_by(clave=key).first():
            counts[(mod,'YA_IMPORTADO')]+=1;continue
        # Comparación con registros anteriores sin origen registrado.
        if mod=='Plan de Calidad':
            day,trn,z,p=identity
            existing=db.query(models.RegistroPlanCalidad).filter_by(fecha=day,turno=trn,zona=z,parametro=p).all()
            if any(str(r.valor)==str(obj.valor) for r in existing):counts[(mod,'DUPLICADO')]+=1;continue
            if existing:
                # Para dos muestras del mismo parámetro, permitir solo si el nombre incluye Muestra.
                if 'Muestra' not in p:
                    counts[(mod,'CONFLICTO')]+=1;issues.append((mod,f'{detail}: registro existente diferente'));continue
        elif mod=='Filtros':
            day,eq,typ,ini,fin=identity
            existing=db.query(models.RegistroLimpiezaFiltro).filter_by(fecha=day,equipo=eq).all()
            if any(norm(r.tipo_limpieza)==norm(typ) and clock(r.hora_inicio_est)==ini and clock(r.hora_final_est)==fin for r in existing):
                counts[(mod,'DUPLICADO')]+=1;continue
            if any(norm(r.tipo_limpieza)==norm(typ) and clock(r.hora_inicio_est)==ini for r in existing):
                counts[(mod,'CONFLICTO')]+=1;issues.append((mod,f'{detail}: evento existente con hora final diferente'));continue
        elif mod=='Limpieza UF':
            day,eq,typ,ini,fin=identity
            existing=db.query(models.RegistroLimpiezaUF).filter_by(fecha=day).all()
            if any(norm(r.equipo)==eq and norm(r.tipo_limpieza)==typ and r.hora_inicio==ini and r.hora_final==fin for r in existing):
                counts[(mod,'DUPLICADO')]+=1;continue
        elif mod=='Contadores 24h':
            if db.query(models.RegistroContador24h).filter_by(fecha=identity).first():
                counts[(mod,'DUPLICADO')]+=1;continue
        counts[(mod,'INSERTADO' if args.aplicar else 'LISTO_PARA_IMPORTAR')]+=1
        if args.aplicar:
            db.add(obj);db.flush()
            db.add(models.RegistroImportacionOrigen(clave=key,modulo=mod,registro_id=obj.id))
    if args.aplicar:db.commit()
report=HERE/'reporte_importacion.txt'
lines=['IMPORTACIÓN PTAP NOVIEMBRE 2026',f'Modo: {"APLICACIÓN EN POSTGRESQL" if args.aplicar else "SIMULACIÓN, SIN ESCRITURAS"}',
       'Origen: Excel noviembre 2026','']
for (mod,status),n in sorted(counts.items()):lines.append(f'{mod} | {status}: {n}')
lines+=['','INCIDENCIAS (primeras 150):']+[f'{mod}: {txt}' for mod,txt in issues[:150]]
report.write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines[:len(counts)+4]));print(f'Informe: {report}')
