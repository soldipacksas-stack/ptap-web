
"""Plan de Calidad V2: almacenamiento seguro sin ALTER sobre tablas históricas."""
import re
from datetime import datetime, date
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, func, or_
from sqlalchemy.orm import Session
from database import Base, engine, get_db
import models

router = APIRouter()

class Version(Base):
    __tablename__ = 'pc_maestra_versiones'
    id = Column(Integer, primary_key=True)
    vigencia_desde = Column(String(10), nullable=False, unique=True)
    descripcion = Column(String(250), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

class Parametro(Base):
    __tablename__ = 'pc_maestra_parametros'
    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey('pc_maestra_versiones.id'), nullable=False, index=True)
    zona = Column(String(150), nullable=False)
    parametro = Column(String(150), nullable=False)
    frecuencia = Column(String(40), nullable=False)
    dia = Column(String(30), nullable=False)
    turno = Column(String(20), nullable=False)
    limite = Column(String(100), nullable=False)
    tipo = Column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint('version_id','zona','parametro',name='uq_pc_maestra_param'),)

class Estado(Base):
    __tablename__ = 'pc_estados'
    id = Column(Integer, primary_key=True)
    registro_id = Column(Integer, ForeignKey('plan_calidad_registros.id', ondelete='CASCADE'), nullable=False, unique=True)
    estado = Column(String(15), nullable=False)
    justificacion = Column(Text)
    version_id = Column(Integer, ForeignKey('pc_maestra_versiones.id'))
    actualizado_en = Column(DateTime, default=datetime.utcnow)

class Auditoria(Base):
    __tablename__ = 'pc_auditoria'
    id = Column(Integer, primary_key=True)
    registro_id = Column(Integer, nullable=False, index=True)
    fecha = Column(String(10), nullable=False)
    turno = Column(String(20), nullable=False)
    operador = Column(String(120), nullable=False)
    anterior = Column(Text, nullable=False)
    nuevo = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

class Vinculo(Base):
    __tablename__ = 'pc_planes_vinculos'
    id = Column(Integer, primary_key=True)
    registro_id = Column(Integer, ForeignKey('plan_calidad_registros.id', ondelete='RESTRICT'), nullable=False)
    plan_id = Column(Integer, ForeignKey('planes_accion_registros.id', ondelete='RESTRICT'), nullable=False, unique=True)
    revisar = Column(String(10), default='No')

class Item(BaseModel):
    zona: str
    parametro: str
    valor: str = ''
    estado: str = 'Resultado'
    justificacion: str = ''
    plan_accion: str = ''
    id: int | None = None

class Lote(BaseModel):
    fecha: str
    turno: str
    operador: str
    registros: list[Item]

class Borrar(BaseModel):
    fecha: str
    turno: str

DIAS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
TURNOS = ['Turno 1','Turno 2','Turno 3']

def validar_fecha_turno(fecha, turno):
    try: f = date.fromisoformat(fecha)
    except (ValueError, TypeError): raise HTTPException(422,'Fecha inválida')
    if turno not in TURNOS: raise HTTPException(422,'Turno inválido')
    return f

def programado(p, fecha, turno):
    f = validar_fecha_turno(fecha, turno)
    if p.turno not in ('Todos',turno): return False
    if p.frecuencia == '2 veces al mes':
        return f.weekday() == 3 and (1 <= f.day <= 7 or 15 <= f.day <= 21)
    if p.frecuencia == 'Semanal': return p.dia == DIAS[f.weekday()]
    return p.dia == 'Todos' or p.dia == DIAS[f.weekday()]

def obtener_version(db, fecha):
    v = db.query(Version).filter(Version.vigencia_desde <= fecha).order_by(Version.vigencia_desde.desc()).first()
    if not v: raise HTTPException(422,'No hay matriz maestra vigente para la fecha')
    return v

def parametros(db, fecha):
    v = obtener_version(db,fecha)
    return v, db.query(Parametro).filter_by(version_id=v.id).order_by(Parametro.id).all()

def limite_efectivo(p):
    # Regla vigente para intensidades UV, sin reescribir versiones históricas.
    if 'intensidad' in p.parametro.casefold() and 'uv' in p.parametro.casefold():
        return '>= 25'
    return p.limite

def ordenar_parametros(ps):
    # Reubicar COT junto a los demás parámetros de su punto de muestreo.
    return sorted(ps, key=lambda p: (p.id if not (p.zona == 'Salida tren filtros agua de servicios' and p.parametro == 'COT') else max((q.id for q in ps if q.zona == p.zona and q.parametro != 'COT'), default=p.id) + 0.5))

def normal_num(valor):
    try: return float(valor.replace(',','.').strip())
    except ValueError: raise HTTPException(422,f'Valor numérico inválido: {valor}')

def evaluar(valor, limite, tipo):
    v = valor.strip()
    if tipo == 'sensorial':
        if v.lower() not in ('pasa','no pasa'): raise HTTPException(422,'Use Pasa o No pasa')
        return 'FUERA DE RANGO' if v.lower() == 'no pasa' else 'Cumple'
    if tipo == 'estado':
        if v.lower() not in ('cumple','no cumple'): raise HTTPException(422,'Use Cumple o No cumple')
        return 'FUERA DE RANGO' if v.lower() == 'no cumple' else 'Cumple'
    n = normal_num(v)
    lim = limite.strip()
    if lim in ('%','-',''): return 'Cumple'  # Sin rango numérico establecido
    m = re.fullmatch(r'([<>]=?)\s*(-?\d+(?:[,.]\d+)?)(?:\s*\w+)?',lim)
    if m:
        op, bound = m.group(1), normal_num(m.group(2))
        ok = {'<':n<bound,'<=':n<=bound,'>':n>bound,'>=':n>=bound}[op]
        return 'Cumple' if ok else 'FUERA DE RANGO'
    m = re.fullmatch(r'(-?\d+(?:[,.]\d+)?)\s*-\s*(-?\d+(?:[,.]\d+)?)',lim)
    if m: return 'Cumple' if normal_num(m.group(1)) <= n <= normal_num(m.group(2)) else 'FUERA DE RANGO'
    raise HTTPException(422,f'Límite sin regla interpretable: {lim}. Revisar matriz maestra antes de guardar.')

def estado_efectivo(item):
    """Compatibilidad con formularios que envían el estado en valor."""
    estado = (item.estado or 'Resultado').strip()
    valor = (item.valor or '').strip()
    if estado == 'Resultado' and valor.upper() in ('NA', 'NC', 'FS', 'E', 'NR', 'PENDIENTE', 'N/A'):
        return {'NA':'NA', 'NC':'NC', 'PENDIENTE':'Pendiente', 'N/A':'NA', 'FS':'FS', 'E':'E', 'NR':'NR'}[valor.upper()]
    return estado

def validar_item(item,p):
    estado = estado_efectivo(item)
    if estado not in ('Resultado','NA','NC','FS','E','NR','Pendiente'):
        raise HTTPException(422,'Estado inválido')
    if estado == 'Pendiente' and not item.justificacion.strip():
        raise HTTPException(422, f'Justificación obligatoria para Pendiente: {p.zona} / {p.parametro}')
    if estado != 'Resultado':
        if (item.valor or '').strip() not in ('', estado, 'N/A' if estado == 'NA' else estado):
            raise HTTPException(422,f'Valor incompatible con {estado}')
        return estado
    if not (item.valor or '').strip():
        raise HTTPException(422,f'Falta valor: {p.zona} / {p.parametro}')
    resultado = evaluar(item.valor,limite_efectivo(p),p.tipo)
    if resultado == 'FUERA DE RANGO' and not item.plan_accion.strip():
        raise HTTPException(422,f'Plan de acción obligatorio: {p.zona} / {p.parametro}')
    return resultado

def serial(r, estado=None):
    return {'id':r.id,'fecha':r.fecha,'turno':r.turno,'operador':r.operador,'zona':r.zona,
            'parametro':r.parametro,'valor':r.valor,'resultado':r.resultado,'limite':r.limite,
            'estado':estado.estado if estado else (r.valor if r.valor in ('N/A','NA','NC','FS','E','NR','Pendiente') else 'Resultado'),
            'justificacion':estado.justificacion if estado else ''}

@router.get('/api/plan-calidad/maestra')
def maestra(fecha: str, turno: str = 'Todos', db: Session=Depends(get_db)):
    date.fromisoformat(fecha)
    v, ps = parametros(db,fecha)
    return {'version':v.id,'maestra':[[p.zona,p.parametro,p.frecuencia,p.dia,p.turno,limite_efectivo(p),p.tipo] for p in ordenar_parametros(ps) if turno=='Todos' or programado(p,fecha,turno)]}

@router.get('/api/plan-calidad/maestra-completa')
def maestra_completa(fecha: str, db:Session=Depends(get_db)):
    v,ps=parametros(db,fecha)
    return {'version':v.id,'maestra':[[p.zona,p.parametro,p.frecuencia,p.dia,p.turno,limite_efectivo(p),p.tipo] for p in ordenar_parametros(ps)]}

@router.get('/api/plan-calidad/registros')
def registros(f_desde:str=Query(...),f_hasta:str=Query(...),turno:str='Todos',db:Session=Depends(get_db)):
    date.fromisoformat(f_desde);date.fromisoformat(f_hasta)
    q=db.query(models.RegistroPlanCalidad).filter(models.RegistroPlanCalidad.fecha>=f_desde,models.RegistroPlanCalidad.fecha<=f_hasta)
    if turno!='Todos':q=q.filter_by(turno=turno)
    rs=q.order_by(models.RegistroPlanCalidad.fecha,models.RegistroPlanCalidad.id).all()
    estados={s.registro_id:s for s in db.query(Estado).filter(Estado.registro_id.in_([r.id for r in rs])).all()} if rs else {}
    return {'total':len(rs),'data':[serial(r,estados.get(r.id)) for r in rs]}

def validar_lote(payload,db,editar=False):
    validar_fecha_turno(payload.fecha,payload.turno)
    if not payload.operador.strip():raise HTTPException(422,'Seleccione operador')
    v,ps=parametros(db,payload.fecha)
    oblig={(p.zona,p.parametro):p for p in ps if programado(p,payload.fecha,payload.turno)}
    recibidos={(x.zona,x.parametro):x for x in payload.registros}
    if len(recibidos)!=len(payload.registros):raise HTTPException(422,'Hay parámetros duplicados en el envío')
    if set(recibidos)!=set(oblig):
        faltan=set(oblig)-set(recibidos);sobran=set(recibidos)-set(oblig)
        raise HTTPException(422,f'Programación no coincide. Faltan: {list(faltan)[:4]}; no programados: {list(sobran)[:4]}')
    # Las cuatro fuentes de captación forman un único conjunto por turno.
    fuentes = [(key, item) for key, item in recibidos.items()
               if key[0].strip().casefold() == 'entrada agua potable'
               and key[1].strip().casefold() in ('agua fuente (pozo 1)', 'agua fuente (pozo 2)',
                   'agua fuente (pozo 3)', 'agua fuente (río)', 'agua fuente (rio)')]
    if fuentes:
        if len(fuentes) != 4:
            raise HTTPException(422, 'Se requieren las cuatro fuentes de captación')
        activos = []
        for _, item in fuentes:
            if estado_efectivo(item) == 'NA':
                continue
            if estado_efectivo(item) != 'Resultado':
                raise HTTPException(422, 'Las fuentes de captación solo admiten porcentaje o NA')
            n = normal_num(item.valor)
            if n == 0:
                item.estado = 'NA'; item.valor = 'NA'
            elif 0 < n <= 100:
                activos.append(n)
            else:
                raise HTTPException(422, 'Los porcentajes de captación deben ser mayores que cero y hasta 100')
        if len(activos) != 3 or abs(sum(activos)-100) > 0.000001:
            raise HTTPException(422, 'Deben existir tres fuentes activas que sumen 100 % y una fuente NA')
    evaluados={key:validar_item(item,oblig[key]) for key,item in recibidos.items()}
    return v,oblig,recibidos,evaluados

def guardar_plan(db,r,item,p,v,resultado,operador,fecha,turno):
    if resultado!='FUERA DE RANGO':return
    plan=models.RegistroPlanAccion(fecha=fecha,turno=turno,modulo='Plan de Calidad',zona=p.zona,parametro=p.parametro,
        valor_registrado=item.valor,limite_esperado=limite_efectivo(p),descripcion_accion=item.plan_accion.strip(),operador=operador)
    db.add(plan);db.flush()
    db.add(Vinculo(registro_id=r.id,plan_id=plan.id))

@router.post('/api/plan-calidad/guardar')
def guardar(payload:Lote,db:Session=Depends(get_db)):
    v,oblig,recibidos,evaluados=validar_lote(payload,db)
    existentes=db.query(models.RegistroPlanCalidad).filter_by(fecha=payload.fecha,turno=payload.turno).all()
    if existentes:raise HTTPException(409,'Ya hay registros para esta fecha y turno. Use Modificar registro.')
    try:
        for key,p in oblig.items():
            item=recibidos[key]; resultado=evaluados[key]
            r=models.RegistroPlanCalidad(fecha=payload.fecha,turno=payload.turno,operador=payload.operador,zona=p.zona,parametro=p.parametro,
               valor=item.valor if estado_efectivo(item)=='Resultado' else estado_efectivo(item),resultado=resultado,limite=limite_efectivo(p))
            db.add(r);db.flush()
            db.add(Estado(registro_id=r.id,estado=estado_efectivo(item),justificacion=item.justificacion.strip() if estado_efectivo(item)!='Resultado' else '',version_id=v.id))
            guardar_plan(db,r,item,p,v,resultado,payload.operador,payload.fecha,payload.turno)
        db.commit()
    except Exception:db.rollback();raise
    return {'status':'ok','guardados':len(oblig)}

@router.put('/api/plan-calidad/editar')
def editar(payload:Lote,db:Session=Depends(get_db)):
    v,oblig,recibidos,evaluados=validar_lote(payload,db,True)
    rs=db.query(models.RegistroPlanCalidad).filter_by(fecha=payload.fecha,turno=payload.turno).with_for_update().all()
    bykey=defaultdict(list)
    for r in rs:bykey[(r.zona,r.parametro)].append(r)
    # Cada lectura debe identificarse explícitamente. Nunca escoger automáticamente
    # un registro histórico cuando existen varios con la misma clave programada.
    if any(k not in bykey for k in oblig):
        raise HTTPException(409,'Registro incompleto. Requiere conciliación histórica antes de editar')
    ids = [recibidos[k].id for k in oblig]
    if any(i is None for i in ids) or len(set(ids)) != len(ids):
        raise HTTPException(409,'La edición requiere un ID único por cada medición programada')
    seleccionados = {}
    for key in oblig:
        item_id = recibidos[key].id
        candidato = next((r for r in bykey[key] if r.id == item_id), None)
        if candidato is None:
            raise HTTPException(409,f'El registro ID {item_id} no pertenece a la muestra seleccionada o cambió desde su consulta')
        seleccionados[key] = candidato
    try:
        for key,p in oblig.items():
            r=seleccionados[key];item=recibidos[key];resultado=evaluados[key]
            s=db.query(Estado).filter_by(registro_id=r.id).first()
            anterior=serial(r,s)
            previo_fuera=r.resultado=='FUERA DE RANGO'
            r.valor=item.valor if estado_efectivo(item)=='Resultado' else estado_efectivo(item)
            r.resultado=resultado;r.limite=limite_efectivo(p)
            if not s:s=Estado(registro_id=r.id,version_id=v.id);db.add(s)
            s.estado=estado_efectivo(item);s.justificacion=item.justificacion.strip() if estado_efectivo(item)!='Resultado' else ''
            nuevo=serial(r,s)
            if anterior['valor']!=nuevo['valor'] or anterior['estado']!=nuevo['estado'] or anterior['justificacion']!=nuevo['justificacion']:
                import json
                db.add(Auditoria(registro_id=r.id,fecha=r.fecha,turno=r.turno,operador=payload.operador,
                    anterior=json.dumps(anterior,ensure_ascii=False),nuevo=json.dumps(nuevo,ensure_ascii=False)))
                vinculos=db.query(Vinculo).filter_by(registro_id=r.id).all()
                for link in vinculos:link.revisar='Si'
                if resultado=='FUERA DE RANGO' and not previo_fuera:guardar_plan(db,r,item,p,v,resultado,payload.operador,payload.fecha,payload.turno)
        db.commit()
    except Exception:db.rollback();raise
    return {'status':'ok','actualizados':len(oblig)}

@router.post('/api/plan-calidad/eliminar')
def eliminar(payload:Borrar,db:Session=Depends(get_db)):
    validar_fecha_turno(payload.fecha,payload.turno)
    rs=db.query(models.RegistroPlanCalidad).filter_by(fecha=payload.fecha,turno=payload.turno).with_for_update().all()
    if not rs:raise HTTPException(404,'No hay registros')
    ids=[r.id for r in rs]
    if db.query(Vinculo).filter(Vinculo.registro_id.in_(ids)).first():
        raise HTTPException(409,'Eliminación bloqueada: hay planes de acción vinculados.')
    # Proteger también planes históricos sin vínculo explícito.
    for r in rs:
        if db.query(models.RegistroPlanAccion).filter_by(fecha=r.fecha,turno=r.turno,modulo='Plan de Calidad',zona=r.zona,parametro=r.parametro).first():
            raise HTTPException(409,'Eliminación bloqueada: existen planes históricos asociados.')
    try:
        db.query(Estado).filter(Estado.registro_id.in_(ids)).delete(synchronize_session=False)
        db.query(models.RegistroPlanCalidad).filter(models.RegistroPlanCalidad.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:db.rollback();raise
    return {'status':'ok','eliminados':len(ids)}

@router.get('/api/plan-calidad/indicadores')
def indicadores(f_desde:str,f_hasta:str,turno:str='Todos',db:Session=Depends(get_db)):
    a=date.fromisoformat(f_desde);b=date.fromisoformat(f_hasta)
    if b<a or (b-a).days>93:raise HTTPException(422,'Seleccione un período máximo de 94 días')
    data=registros(f_desde,f_hasta,turno,db)['data']
    mapa=defaultdict(list)
    for r in data:mapa[(r['fecha'],r['turno'],r['zona'],r['parametro'])].append(r)
    from datetime import timedelta
    total={'programados':0,'realizados':0,'na':0,'pendientes':0,'sin_estado':0}
    detalle=[];dia=a
    while dia<=b:
        for t in (TURNOS if turno=='Todos' else [turno]):
            _,ps=parametros(db,dia.isoformat())
            c=dict.fromkeys(total,0)
            for p in ps:
                if not programado(p,dia.isoformat(),t):continue
                c['programados']+=1
                matches=mapa[(dia.isoformat(),t,p.zona,p.parametro)]
                if len(matches)!=1:c['sin_estado']+=1;continue
                r=matches[0];state=r['estado']
                if state=='Resultado':c['realizados']+=1
                elif state in ('NA','NC'):c['na']+=1
                elif state=='Pendiente':c['pendientes']+=1
                else:c['sin_estado']+=1
            for k in total:total[k]+=c[k]
            c.update({'fecha':dia.isoformat(),'turno':t,
                      'documental':round(100*(c['realizados']+c['na']+c['pendientes'])/c['programados'],1) if c['programados'] else 100,
                      'ejecucion':round(100*c['realizados']/c['programados'],1) if c['programados'] else 100})
            detalle.append(c)
        dia+=timedelta(days=1)
    total['documental']=round(100*(total['realizados']+total['na']+total['pendientes'])/total['programados'],1) if total['programados'] else 100
    total['ejecucion']=round(100*total['realizados']/total['programados'],1) if total['programados'] else 100
    return {'total':total,'detalle':detalle}

def iniciar(maestra):
    Base.metadata.create_all(bind=engine, tables=[Version.__table__,Parametro.__table__,Estado.__table__,Auditoria.__table__,Vinculo.__table__])
    with Session(engine) as db:
        if db.query(Version).count():return
        v=Version(vigencia_desde='2000-01-01',descripcion='Matriz inicial importada del código existente; verificar límites oficiales')
        db.add(v);db.flush()
        for zona,parametro,frecuencia,dia,turno,limite,tipo in maestra:
            db.add(Parametro(version_id=v.id,zona=zona,parametro=parametro,frecuencia=frecuencia,dia=dia,turno=turno,limite=limite,tipo=tipo))
        db.commit()

