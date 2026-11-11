"""Auditoría de importación PTAP. NO escribe en PostgreSQL ni en el Excel.
Uso: python simular.py [archivo.xlsx]
Opcional: DATABASE_URL=postgresql://... para detectar duplicados de Plan Calidad y Filtros.
"""
import csv, os, sys, re, json, zipfile, unicodedata
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
HERE=Path(__file__).resolve().parent
SOURCE=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'fuente_noviembre_2026.xlsx'

def colnum(ref):
    s=re.match('[A-Z]+',ref).group(); n=0
    for c in s:n=n*26+ord(c)-64
    return n

def parse_excel(path):
    with zipfile.ZipFile(path) as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            r=ET.fromstring(z.read('xl/sharedStrings.xml'))
            ss=[''.join(x.text or '' for x in si.findall('.//m:t',NS)) for si in r.findall('m:si',NS)]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        relroot=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rel={x.attrib['Id']:x.attrib['Target'].lstrip('/') for x in relroot}
        for sh in book.findall('.//m:sheet',NS):
            name=sh.attrib['name'];
            if name not in ('Plan Calidad','Control Contadores 24h','LimpiezaFiltrosCarbón','Limpieza  UF'):continue
            target=rel[sh.attrib['{'+NS['r']+'}id']]
            target=target if target.startswith('xl/') else 'xl/'+target
            root=ET.fromstring(z.read(target)); rows=[]
            for row in root.findall('.//m:sheetData/m:row',NS):
                cells={}
                for c in row.findall('m:c',NS):
                    v=c.find('m:v',NS); inline=c.find('m:is',NS)
                    if v is None and inline is None:continue
                    value=(ss[int(v.text)] if c.get('t')=='s' else v.text) if v is not None else ''.join(t.text or '' for t in inline.findall('.//m:t',NS))
                    if value is not None and str(value).strip():cells[colnum(c.attrib['r'])]=value
                rows.append((int(row.attrib['r']),cells))
            yield name,rows

def exceldate(v):
    try:return (datetime(1899,12,30)+timedelta(days=float(v))).date().isoformat()
    except (TypeError,ValueError):return None

def clock(v):
    if v is None:return ''
    try:
        f=float(v)
        if 0<=f<1:
            minutes=round(f*1440)%1440
            return f'{minutes//60:02d}:{minutes%60:02d}'
    except (ValueError,TypeError):pass
    return str(v).strip()

def norm(v):
    s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+','',s)

def row_out(mod,sheet,row,date,point,parameter,value,extra='',status='SIN_VERIFICAR_DB',reason=''):
    return dict(modulo=mod,hoja=sheet,fila_excel=row,fecha=date or '',punto_equipo=point or '',parametro_tipo=parameter or '',valor=str(value or ''),detalle=extra,estado=status,motivo=reason)

