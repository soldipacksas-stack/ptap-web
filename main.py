from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional, Any
from collections import defaultdict
import openpyxl
import os

from database import engine, Base, get_db
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Control Operacional PTAP - Web")
templates = Jinja2Templates(directory="templates")

# Lista oficial de operadores PTAP
OPERADORES_PTAP = [
    "BALLEN MERCHAN DIEGO ARMANDO",
    "CORDOBA JIMENEZ HECTOR ENRIQUE",
    "GARCIA SANCHEZ RICARDO ANDRES",
    "GOMEZ CACERES RICARDO ALFONSO",
    "MELO DIAZ BRYAM ANDRES",
    "MENDOZA CHARRY KEVIN JHOJAN",
    "OSPINA HERNANDEZ JORGE ALEJANDRO",
    "ROBAYO CASTRO DANIELA",
    "RODRIGUEZ PUENTES JAIME ANDRES",
    "RODRIGUEZ VELANDIA JENNY PAOLA",
    "SOLIS YEPES JAVIER MAURICIO",
    "ARTENGA SANDOVAL NELSON DAVID",
    "PAMPLONA FUQUENE JULIAN DANIEL"
]

# Maestra del Plan de Calidad PTAP (108 registros oficiales de la matriz)
MAESTRA_PLAN_CALIDAD = [('Entrada Agua Potable', 'Agua Fuente (Río)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Agua Fuente (Pozo 1)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Agua Fuente (Pozo 2)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Agua Fuente (Pozo 3)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Cloro residual (Muestra 1)', 'Turno', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Entrada Agua Potable', 'Cloro residual (Muestra 2)', 'Turno', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Entrada Agua Potable', 'pH', 'Turno', 'Todos', 'Todos', '6,5 - 7,5', 'numero'), ('Entrada Agua Potable', 'Hierro total (Fe)', 'Diario', 'Todos', 'Turno 1', '0 - 0,1', 'numero'), ('Entrada Agua Potable', 'Evaluación Sensorial', 'Diario', 'Todos', 'Todos', 'Pasa / No pasa', 'sensorial'), ('Entrada Agua Potable', 'Turbiedad (Lab)', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Entrada Agua Potable', 'Turbiedad (Linea)', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Entrada Agua Potable', 'Sólidos disueltos totales (TDS)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Entrada Agua Potable', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Entrada Agua Potable', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Entrada Agua Potable', 'Dureza Total', 'Semanal', 'Miércoles', 'Turno 1', '0 - 100', 'numero'), ('Entrada Agua Potable', 'Cloruros', 'Semanal', 'Miércoles', 'Turno 1', '0 - 250', 'numero'), ('Entrada Agua Potable', 'Diferencial de Presión Filtro 1', 'Semanal', 'Miércoles', 'Turno 1', '0 - 10', 'numero'), ('Entrada Agua Potable', 'Diferencial de Presión Filtro 2', 'Semanal', 'Miércoles', 'Turno 1', '0 - 10', 'numero'), ('Entrada Agua Potable', 'Sulfatos', 'Semanal', 'Martes', 'Turno 1', '0 - 50', 'numero'), ('Entrada Agua Potable', 'Aluminio (Al)', 'Semanal', 'Martes', 'Turno 1', '0 - 0,1', 'numero'), ('Entrada Agua Potable', 'Alcalinidad Total', 'Semanal', 'Martes', 'Turno 1', '0 - 90', 'numero'), ('Entrada Agua Potable', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Entrada Agua Potable', 'COT (Pozo 1)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Pozo 2)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Pozo 3)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Rio)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Entrada agua potable)', 'Semanal', 'Miércoles', 'Turno 2', '0 - 5', 'numero'), ('Agua potable para Servicios Generales', 'Cloro residual', 'Diario', 'Todos', 'Turno 1', '0,5 - 2', 'numero'), ('Casino principal', 'Cloro residual', 'Semanal', 'Jueves', 'Turno 1', '0,5 - 2', 'numero'), ('Baño envasado', 'Cloro residual', 'Semanal', 'Jueves', 'Turno 1', '0,5 - 2', 'numero'), ('Casino Postobón', 'Cloro residual', 'Semanal', 'Jueves', 'Turno 1', '0,5 - 2', 'numero'), ('Agua Suavizada', 'Dureza Total', 'Diario', 'Todos', 'Turno 1', '0 - 5', 'numero'), ('Agua Suavizada', 'pH', 'Diario', 'Todos', 'Turno 1', '6,5 - 8', 'numero'), ('Agua Suavizada', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Agua Suavizada', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Agua Suavizada', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Agua Suavizada', 'Solidos disueltos totales (TDS)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Almacenamiento de agua potable para proceso', 'Cloro residual', 'Diario', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Tanque de almacenamiento PTAP cervecera', 'Cloro residual', 'Diario', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Tanque de almacenamiento PTAP cervecera', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 3', 'numero'), ('Tanque de almacenamiento PATP Servicios', 'Cloro residual', 'Diario', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Tanque de almacenamiento PATP Servicios', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 3', 'numero'), ('Filtracion por carbon agua cervecera', 'Cloro residual F C1', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua cervecera', 'Cloro residual F C2', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua cervecera', 'Cloro residual F C3', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua de servicios', 'Cloro residual F C1', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua de servicios', 'Cloro residual F C2', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua de servicios', 'Cloro residual F C3', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua cervecera', 'Cloro residual (Lab)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua cervecera', 'Cloro residual (Linea)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua cervecera', 'Concentración dioxido de cloro (Lab)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Salida tren filtros agua cervecera', 'Concentración dioxido de cloro (Linea)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Salida tren filtros agua cervecera', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 2', 'numero'), ('Salida tren filtros agua de servicios', 'Cloro residual (Lab)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua de servicios', 'Cloro residual (Linea)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua de servicios', 'Concentración dioxido de cloro (Lab)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Salida tren filtros agua de servicios', 'Concentración dioxido de cloro (Linea)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'pH (Muestra 1)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'pH (Muestra 2)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Cloro residual', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Evaluación Sensorial', 'Diario', 'Todos', 'Todos', 'Pasa / No pasa', 'sensorial'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Intensidad lampara UV 1', 'Diario', 'Todos', 'Todos', '0 - 25', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Intensidad lampara UV 2', 'Diario', 'Todos', 'Todos', '0 - 25', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Dureza Total', 'Semanal', 'Miércoles', 'Turno 1', '0 - 90', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Cloruros', 'Semanal', 'Miércoles', 'Turno 1', '0 - 70', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Solidos disueltos totales', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Sulfatos', 'Semanal', 'Martes', 'Turno 1', '0 - 50', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Alcalinidad Total', 'Semanal', 'Martes', 'Turno 1', '0 - 90', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Aluminio (Al)', 'Semanal', 'Martes', 'Turno 1', '0 - 0,1', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Dióxido de Cloro', 'Diario', 'Todos', 'Todos', '0 - 0,4', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'pH (Muestra 1)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'pH (Muestra 2)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Cloro residual', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Evaluación Sensorial', 'Diario', 'Todos', 'Todos', 'Pasa / No pasa', 'sensorial'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Intensidad lampara UV 1', 'Diario', 'Todos', 'Todos', '0 - 25', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Dureza Total', 'Semanal', 'Miércoles', 'Turno 1', '< 90 ppm', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Cloruros', 'Semanal', 'Miércoles', 'Turno 1', '0 - 70', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Solidos disueltos totales', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Sulfatos', 'Semanal', 'Martes', 'Turno 1', '0 - 50', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Alcalinidad Total', 'Semanal', 'Martes', 'Turno 1', '0 - 90', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Aluminio (Al)', 'Semanal', 'Martes', 'Turno 1', '0 - 0,1', 'numero'), ('Cuarto generación dióxido de cloro', 'Nivel de los tanques buffer', 'Diario', 'Todos', 'Todos', 'Cumple / No cumple', 'estado')]


class ItemRegistro(BaseModel):
    zona: str
    parametro: str
    valor: Any  
    limite: Optional[str] = "-"
    plan_accion: Optional[str] = ""  # <--- Este campo es el que recibe el formulario HTML

class PayloadGuardarPlan(BaseModel):
    fecha: str
    turno: str
    operador: str
    registros: List[ItemRegistro]


class ItemEditarRegistro(BaseModel):
    id: int
    valor: Any  # <--- MODIFICADO: Flexible para evitar errores 422 en la edición


class PayloadEditarRegistros(BaseModel):
    fecha: str
    turno: str
    registros: List[ItemEditarRegistro]


class PayloadEliminarRegistros(BaseModel):
    fecha: str
    turno: str

class PayloadExcepcion(BaseModel):
    fecha: str
    turno: str
    zona: str
    parametro: str
    estado: str
    observacion: Optional[str] = ""


# DASHBOARD GERENCIAL: endpoints de solo lectura.
@app.get("/", response_class=HTMLResponse)
def vista_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"request": request})

@app.get("/api/dashboard/resumen")
def api_dashboard_resumen(desde: Optional[str] = None, hasta: Optional[str] = None,
                          turno: str = "Todos", zona: str = "Todas",
                          db: Session = Depends(get_db)):
    try:
        fin = date.fromisoformat(hasta) if hasta else date.today()
        inicio = date.fromisoformat(desde) if desde else fin - timedelta(days=29)
    except ValueError:
        raise HTTPException(422, "Fecha inválida; use AAAA-MM-DD")
    if inicio > fin or (fin - inicio).days > 366:
        raise HTTPException(422, "Rango de fechas inválido")
    q = db.query(models.RegistroPlanCalidad).filter(
        models.RegistroPlanCalidad.fecha >= inicio.isoformat(),
        models.RegistroPlanCalidad.fecha <= fin.isoformat())
    if turno != "Todos":
        q = q.filter(models.RegistroPlanCalidad.turno == turno)
    if zona != "Todas":
        q = q.filter(models.RegistroPlanCalidad.zona == zona)
    registros = q.all()
    estados_validos = {"cumple", "fuera de rango", "no cumple"}
    validos = [r for r in registros if (r.resultado or "").strip().lower() in estados_validos]
    conformes = sum((r.resultado or "").strip().lower() == "cumple" for r in validos)
    series = defaultdict(lambda: [0, 0])
    areas = defaultdict(lambda: [0, 0])
    for r in validos:
        ok = int((r.resultado or "").strip().lower() == "cumple")
        series[r.fecha][0] += ok; series[r.fecha][1] += 1
        areas[r.zona][0] += ok; areas[r.zona][1] += 1
    # La programación de análisis exige reconciliación con cada medición
    # esperada; no publicar un porcentaje de ejecución sin ese cálculo.
    alertas = [{"id": r.id, "fecha": r.fecha, "turno": r.turno,
                "zona": r.zona, "parametro": r.parametro,
                "valor": r.valor, "limite": r.limite}
               for r in registros if (r.resultado or "").strip().lower() in
               {"fuera de rango", "no cumple"}]
    alertas.sort(key=lambda x: (x["fecha"], x["id"]), reverse=True)
    return {"desde": inicio.isoformat(), "hasta": fin.isoformat(),
            "registros": len(registros), "validos": len(validos),
            "conformes": conformes, "no_conformes": len(validos)-conformes,
            "cumplimiento": round(conformes*100/len(validos), 1) if validos else None,
            "ejecucion": None, "pendientes": None,
            "tendencia": [{"fecha": k, "porcentaje": round(v[0]*100/v[1],1)}
                          for k,v in sorted(series.items())],
            "zonas": [{"zona": k, "porcentaje": round(v[0]*100/v[1],1)}
                      for k,v in sorted(areas.items())],
            "alertas": alertas[:12],
            "zonas_disponibles": sorted({r[0] for r in MAESTRA_PLAN_CALIDAD})}

@app.get("/plan-calidad", response_class=HTMLResponse)
def vista_plan_calidad(request: Request):
    return templates.TemplateResponse(request, "plan_calidad.html", {
        "operadores": OPERADORES_PTAP,
        "maestra": MAESTRA_PLAN_CALIDAD
    })

@app.get("/api/plan-calidad/maestra")
def obtener_maestra(fecha: Optional[str] = None, turno: Optional[str] = None):
    dia_semana_esp = "Todos"
    dt = None
    if fecha:
        try:
            dt = datetime.strptime(fecha, "%Y-%m-%d")
            dias_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
            dia_semana_esp = dias_map.get(dt.weekday(), "Todos")
        except Exception:
            dt = None

    maestra_filtrada = []
    for zona, parametro, frecuencia, dia_esp, trn, limite, tipo in MAESTRA_PLAN_CALIDAD:
        coincide_dia = dia_esp == "Todos" or dia_esp == dia_semana_esp
        if frecuencia == "2 veces al mes":
            coincide_dia = bool(dt and dt.weekday() == 3 and (1 <= dt.day <= 7 or 15 <= dt.day <= 21))
        coincide_turno = (trn == "Todos" or not turno or turno == "Todos" or trn == turno)
        if coincide_dia and coincide_turno:
            maestra_filtrada.append((zona, parametro, frecuencia, dia_esp, trn, limite, tipo))
    return {"maestra": maestra_filtrada}


@app.get("/api/plan-calidad/registros")
def consultar_registros(
    f_desde: str = Query(...),
    f_hasta: str = Query(...),
    turno: str = Query("Todos"),
    db: Session = Depends(get_db)
):
    query = db.query(models.RegistroPlanCalidad).filter(
        models.RegistroPlanCalidad.fecha >= f_desde,
        models.RegistroPlanCalidad.fecha <= f_hasta
    )
    if turno != "Todos":
        query = query.filter(models.RegistroPlanCalidad.turno == turno)
    
    registros = query.order_by(models.RegistroPlanCalidad.fecha.desc(), models.RegistroPlanCalidad.id.desc()).all()
    return {"total": len(registros), "data": registros}

@app.post("/api/plan-calidad/guardar")
def guardar_plan_calidad(payload: PayloadGuardarPlan, db: Session = Depends(get_db)):
    nuevos_modelos = []
    for item in payload.registros:
        val = str(item.valor).strip() if item.valor is not None else ""
        if not val:
            continue
        
        resultado = "Cumple"
        if val.lower() in ["no pasa", "no cumple"]:
            resultado = "FUERA DE RANGO"
        
        reg = models.RegistroPlanCalidad(
            fecha=payload.fecha,
            turno=payload.turno,
            operador=payload.operador,
            zona=item.zona,
            parametro=item.parametro,
            valor=val,
            resultado=resultado,
            limite=item.limite if item.limite else "-"
        )
        nuevos_modelos.append(reg)

    if not nuevos_modelos:
        raise HTTPException(status_code=400, detail="No se enviaron datos válidos para guardar.")

    db.add_all(nuevos_modelos)
    db.commit()

    sincronizar_excel(payload, nuevos_modelos)

    return {"status": "ok", "guardados": len(nuevos_modelos)}

@app.post("/api/plan-calidad/excepcion")
def guardar_excepcion(payload: PayloadExcepcion, db: Session = Depends(get_db)):
    exc = models.ExcepcionPlanCalidad(
        fecha=payload.fecha,
        turno=payload.turno,
        zona=payload.zona,
        parametro=payload.parametro,
        estado=payload.estado,
        observacion=payload.observacion
    )
    db.add(exc)
    db.commit()
    return {"status": "ok", "message": "Excepción guardada correctamente"}


# ==========================================================
# ADMINISTRACIÓN DE REGISTROS DEL PLAN DE CALIDAD
# ==========================================================

@app.put("/api/plan-calidad/editar")
def editar_registros_plan_calidad(
    payload: PayloadEditarRegistros,
    db: Session = Depends(get_db)
):
    try:
        datetime.strptime(payload.fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Use AAAA-MM-DD.")

    if payload.turno not in ["Turno 1", "Turno 2", "Turno 3"]:
        raise HTTPException(status_code=400, detail="Turno inválido.")

    if not payload.registros:
        raise HTTPException(status_code=400, detail="No hay registros para actualizar.")

    ids = [item.id for item in payload.registros]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="La solicitud contiene registros duplicados.")

    try:
        registros_db = db.query(models.RegistroPlanCalidad).filter(
            models.RegistroPlanCalidad.id.in_(ids),
            models.RegistroPlanCalidad.fecha == payload.fecha,
            models.RegistroPlanCalidad.turno == payload.turno
        ).all()

        encontrados = {registro.id: registro for registro in registros_db}
        faltantes = set(ids) - set(encontrados)
        if faltantes:
            raise HTTPException(
                status_code=404,
                detail="Uno o más registros ya no existen o no corresponden a la fecha y turno seleccionados."
            )

        for item in payload.registros:
            nuevo_valor = str(item.valor).strip() if item.valor is not None else ""
            if not nuevo_valor:
                raise HTTPException(status_code=400, detail="Los valores no pueden quedar vacíos.")

            registro = encontrados[item.id]
            registro.valor = nuevo_valor
            registro.resultado = (
                "FUERA DE RANGO"
                if nuevo_valor.lower() in ["no pasa", "no cumple"]
                else "Cumple"
            )

        db.commit()
        return {
            "status": "ok",
            "actualizados": len(payload.registros),
            "message": "Registros actualizados correctamente."
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar registros: {str(exc)}")


@app.post("/api/plan-calidad/eliminar")
def eliminar_registros_plan_calidad(
    payload: PayloadEliminarRegistros,
    db: Session = Depends(get_db)
):
    try:
        datetime.strptime(payload.fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Use AAAA-MM-DD.")

    if payload.turno not in ["Turno 1", "Turno 2", "Turno 3"]:
        raise HTTPException(status_code=400, detail="Turno inválido.")

    try:
        consulta = db.query(models.RegistroPlanCalidad).filter(
            models.RegistroPlanCalidad.fecha == payload.fecha,
            models.RegistroPlanCalidad.turno == payload.turno
        )
        cantidad = consulta.count()

        if cantidad == 0:
            raise HTTPException(
                status_code=404,
                detail="No existen registros para esa fecha y turno."
            )

        consulta.delete(synchronize_session=False)
        db.commit()

        return {
            "status": "ok",
            "eliminados": cantidad,
            "message": "Registros eliminados correctamente."
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar registros: {str(exc)}")

def sincronizar_excel(payload: PayloadGuardarPlan, registros):
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Plan_Calidad"
    encabezados = ["Fecha", "Turno", "Operador", "Zona", "Parámetro", "Valor", "Resultado"]

    try:
        if os.path.exists(nombre_archivo):
            wb = openpyxl.load_workbook(nombre_archivo)
            ws = wb[nombre_hoja] if nombre_hoja in wb.sheetnames else wb.create_sheet(title=nombre_hoja)
            if ws.max_row == 1 and ws.cell(1, 1).value is None:
                ws.append(encabezados)
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = nombre_hoja
            ws.append(encabezados)

        for r in registros:
            ws.append([r.fecha, r.turno, r.operador, r.zona, r.parametro, r.valor, r.resultado])

        wb.save(nombre_archivo)
        wb.close()
    except Exception as e:
        print(f"Error al sincronizar con Excel: {e}")

# --- MÓDULO: LIMPIEZA Y ESTERILIZACIÓN DE FILTROS ---

class PayloadLimpiezaFiltro(BaseModel):
    fecha: str
    equipo: str
    operador: str
    tipo_limpieza: str
    temperatura: Optional[str] = "N/A"
    hora_muestra_antes: Optional[str] = "N/A"
    hora_inicio_est: Optional[str] = "N/A"
    hora_final_est: Optional[str] = "N/A"
    hora_muestra_despues: Optional[str] = "N/A"
    perdida_carbon: Optional[str] = "No"
    agua_inicial: Optional[float] = 0.0
    agua_final: Optional[float] = 0.0
    cloro: Optional[str] = ""
    turbidez: Optional[str] = ""

@app.get("/filtros", response_class=HTMLResponse)
def vista_limpieza_filtros(request: Request):
    return templates.TemplateResponse(request, "limpieza_filtros.html", {
        "request": request,
        "operadores": OPERADORES_PTAP,
        "filtros": ["F121", "F122", "F123", "F221", "F222", "F223"]
    })

@app.get("/api/filtros/registros")
def consultar_registros_filtros(db: Session = Depends(get_db)):
    registros = db.query(models.RegistroLimpiezaFiltro).order_by(models.RegistroLimpiezaFiltro.id.desc()).all()
    return {"data": registros}

@app.post("/api/filtros/guardar")
def guardar_limpieza_filtro(payload: PayloadLimpiezaFiltro, db: Session = Depends(get_db)):
    consumo = max(0.0, round(payload.agua_final - payload.agua_inicial, 2))
    
    nuevo_reg = models.RegistroLimpiezaFiltro(
        fecha=payload.fecha,
        equipo=payload.equipo,
        operador=payload.operador,
        tipo_limpieza=payload.tipo_limpieza,
        temperatura=payload.temperatura,
        hora_muestra_antes=payload.hora_muestra_antes,
        hora_inicio_est=payload.hora_inicio_est,
        hora_final_est=payload.hora_final_est,
        hora_muestra_despues=payload.hora_muestra_despues,
        perdida_carbon=payload.perdida_carbon,
        agua_inicial=payload.agua_inicial,
        agua_final=payload.agua_final,
        consumo_agua=consumo,
        cloro=payload.cloro,
        turbidez=payload.turbidez
    )
    db.add(nuevo_reg)
    db.commit()

    sincronizar_excel_filtros(payload, consumo)
    return {"status": "ok"}

@app.put("/api/filtros/actualizar/{registro_id}")
def actualizar_limpieza_filtro(registro_id: int, payload: PayloadLimpiezaFiltro, db: Session = Depends(get_db)):
    reg = db.query(models.RegistroLimpiezaFiltro).filter(models.RegistroLimpiezaFiltro.id == registro_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado en la base de datos.")
    
    consumo = max(0.0, round(payload.agua_final - payload.agua_inicial, 2))
    
    # Actualización de datos del registro
    reg.fecha = payload.fecha
    reg.equipo = payload.equipo
    reg.operador = payload.operador
    reg.tipo_limpieza = payload.tipo_limpieza
    reg.temperatura = payload.temperatura
    reg.hora_muestra_antes = payload.hora_muestra_antes
    reg.hora_inicio_est = payload.hora_inicio_est
    reg.hora_final_est = payload.hora_final_est
    reg.hora_muestra_despues = payload.hora_muestra_despues
    reg.perdida_carbon = payload.perdida_carbon
    reg.agua_inicial = payload.agua_inicial
    reg.agua_final = payload.agua_final
    reg.consumo_agua = consumo
    reg.cloro = payload.cloro
    reg.turbidez = payload.turbidez

    db.commit()

    return {"status": "ok", "message": "Registro actualizado correctamente"}

@app.delete("/api/filtros/eliminar/{registro_id}")
def eliminar_limpieza_filtro(registro_id: int, db: Session = Depends(get_db)):
    reg = db.query(models.RegistroLimpiezaFiltro).filter(models.RegistroLimpiezaFiltro.id == registro_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado en la base de datos.")
    
    db.delete(reg)
    db.commit()

    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Limpieza_Filtros"
    try:
        if os.path.exists(nombre_archivo):
            wb = openpyxl.load_workbook(nombre_archivo)
            if nombre_hoja in wb.sheetnames:
                ws = wb[nombre_hoja]
                for row_idx in range(2, ws.max_row + 1):
                    f_val = str(ws.cell(row=row_idx, column=1).value)
                    eq_val = str(ws.cell(row=row_idx, column=2).value)
                    h_fin_val = str(ws.cell(row=row_idx, column=8).value)
                    
                    if f_val == str(reg.fecha) and eq_val == str(reg.equipo) and h_fin_val == str(reg.hora_final_est):
                        ws.delete_rows(row_idx)
                        break
                wb.save(nombre_archivo)
            wb.close()
    except Exception as e:
        print(f"Error al eliminar fila en Excel de filtros: {e}")

    return {"status": "ok", "message": "Registro eliminado correctamente"}

def sincronizar_excel_filtros(payload, consumo):
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Limpieza_Filtros"
    encabezados = [
        "Fecha", "Equipo", "Operador", "Tipo Limpieza", "Temperatura (°C)",
        "Hora Muestra Antes", "Hora Inicio Est.", "Hora Final Est.", "Hora Muestra Después", 
        "Pérdida Carbón", "Agua Inicial", "Agua Final", "Consumo (m³)", "Cloro", "Turbidez"
    ]
    try:
        if os.path.exists(nombre_archivo):
            wb = openpyxl.load_workbook(nombre_archivo)
            ws = wb[nombre_hoja] if nombre_hoja in wb.sheetnames else wb.create_sheet(title=nombre_hoja)
            if ws.max_row == 1 and ws.cell(1, 1).value is None:
                ws.append(encabezados)
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = nombre_hoja
            ws.append(encabezados)

        ws.append([
            payload.fecha, payload.equipo, payload.operador, payload.tipo_limpieza, payload.temperatura,
            payload.hora_muestra_antes, payload.hora_inicio_est, payload.hora_final_est,
            payload.hora_muestra_despues, payload.perdida_carbon, payload.agua_inicial,
            payload.agua_final, consumo, payload.cloro, payload.turbidez
        ])
        wb.save(nombre_archivo)
        wb.close()
    except Exception as e:
        print(f"Error sincronizando Excel de filtros: {e}")


# --- MÓDULO: CONTADORES 24H ---

class PayloadContadores24h(BaseModel):
    fecha: str
    operador: str
    lecturas: dict

@app.get("/contadores", response_class=HTMLResponse)
def ver_contadores(request: Request):
    return templates.TemplateResponse(request, "contadores.html", {
        "request": request,
        "operadores": OPERADORES_PTAP
    })

@app.get("/api/contadores/registros")
def consultar_registros_contadores(db: Session = Depends(get_db)):
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Contadores_24h"
    resultado = []
    
    if os.path.exists(nombre_archivo):
        try:
            wb = openpyxl.load_workbook(nombre_archivo, read_only=True, data_only=True)
            if nombre_hoja in wb.sheetnames:
                ws = wb[nombre_hoja]
                filas = list(ws.iter_rows(values_only=True))
                if len(filas) > 1:
                    encabezados = filas[0]
                    for row in filas[1:]:
                        if not row or not any(row): continue
                        fecha = row[0]
                        operador = row[1]
                        lecturas_dict = {}
                        for i in range(2, len(encabezados)):
                            if i < len(row):
                                lecturas_dict[str(encabezados[i])] = row[i]
                        resultado.append({
                            "fecha": str(fecha),
                            "operador": str(operador),
                            "lecturas": lecturas_dict
                        })
            wb.close()
        except Exception as e:
            print(f"Error leyendo contadores de Excel: {e}")
            
    return {"data": resultado}

@app.post("/api/contadores/guardar")
def guardar_contadores_24h(payload: PayloadContadores24h):
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Contadores_24h"
    
    try:
        ultima_fila = {}
        if os.path.exists(nombre_archivo):
            wb_old = openpyxl.load_workbook(nombre_archivo, read_only=True, data_only=True)
            if nombre_hoja in wb_old.sheetnames:
                ws_old = wb_old[nombre_hoja]
                rows = list(ws_old.iter_rows(values_only=True))
                if len(rows) > 1:
                    headers = rows[0]
                    last_vals = rows[-1]
                    for i, h in enumerate(headers):
                        if i < len(last_vals):
                            ultima_fila[str(h)] = last_vals[i]
            wb_old.close()

        encabezados = ["Fecha", "Operador"]
        fila_datos = [payload.fecha, payload.operador]

        for medidor, val in payload.lecturas.items():
            is_nivel = "Nivel" in medidor
            if is_nivel:
                encabezados.append(medidor)
                fila_datos.append(val)
            else:
                encabezados.append(f"{medidor} - Lectura")
                encabezados.append(f"{medidor} - Total")
                fila_datos.append(val)
                
                val_anterior = float(ultima_fila.get(f"{medidor} - Lectura", val))
                consumo = round(max(0.0, val - val_anterior), 2)
                fila_datos.append(consumo)

        wb = openpyxl.load_workbook(nombre_archivo) if os.path.exists(nombre_archivo) else openpyxl.Workbook()
        ws = wb[nombre_hoja] if nombre_hoja in wb.sheetnames else wb.create_sheet(title=nombre_hoja)
        
        if ws.max_row == 1 and ws.cell(1, 1).value is None:
            ws.append(encabezados)
            
        ws.append(fila_datos)
        wb.save(nombre_archivo)
        wb.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- MÓDULO: BITÁCORA ---

class PayloadBitacora(BaseModel):
    fecha: str
    turno: str
    operador: str
    reporte: str

@app.get("/bitacora", response_class=HTMLResponse)
def ver_bitacora(request: Request):
    return templates.TemplateResponse(request, "bitacora.html", {
        "request": request,
        "operadores": OPERADORES_PTAP
    })

@app.get("/api/bitacora/registros")
def consultar_registros_bitacora():
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Bitacora"
    resultado = []
    
    if os.path.exists(nombre_archivo):
        try:
            wb = openpyxl.load_workbook(nombre_archivo, read_only=True, data_only=True)
            if nombre_hoja in wb.sheetnames:
                ws = wb[nombre_hoja]
                filas = list(ws.iter_rows(values_only=True))
                for row in filas[1:]:
                    if not row or not any(row): continue
                    resultado.insert(0, {
                        "fecha": str(row[0]),
                        "turno": str(row[1]),
                        "operador": str(row[2]),
                        "reporte": str(row[3])
                    })
            wb.close()
        except Exception as e:
            print(f"Error leyendo bitácora de Excel: {e}")
            
    return {"data": resultado}

@app.post("/api/bitacora/guardar")
def guardar_bitacora(payload: PayloadBitacora):
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Bitacora"
    encabezados = ["Fecha", "Turno", "Operador", "Reporte"]
    
    try:
        wb = openpyxl.load_workbook(nombre_archivo) if os.path.exists(nombre_archivo) else openpyxl.Workbook()
        ws = wb[nombre_hoja] if nombre_hoja in wb.sheetnames else wb.create_sheet(title=nombre_hoja)
        
        if ws.max_row == 1 and ws.cell(1, 1).value is None:
            ws.append(encabezados)
            
        ws.append([payload.fecha, payload.turno, payload.operador, payload.reporte])
        wb.save(nombre_archivo)
        wb.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- MÓDULO: LIMPIEZA UF ---

class PayloadLimpiezaUF(BaseModel):
    fecha: str
    equipo: str
    operador: str
    tipo_limpieza: str
    hora_inicio: str
    hora_final: str
    concentracion_1: str
    concentracion_2: str
    agua_inicial: float
    agua_final: float
    turbiedad: str
    ph_final: str
    observaciones: Optional[str] = ""

@app.get("/limpieza-uf", response_class=HTMLResponse)
def ver_limpieza_uf(request: Request):
    return templates.TemplateResponse(request, "limpieza_uf.html", {
        "request": request,
        "operadores": OPERADORES_PTAP,
        "equipos": ["U.F 111", "U.F 112", "U.F 211", "U.F 212"]
    })

@app.get("/api/limpieza-uf/registros")
def consultar_registros_limpieza_uf():
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Limpieza_UF"
    resultado = []
    
    if os.path.exists(nombre_archivo):
        try:
            wb = openpyxl.load_workbook(nombre_archivo, read_only=True, data_only=True)
            if nombre_hoja in wb.sheetnames:
                ws = wb[nombre_hoja]
                filas = list(ws.iter_rows(values_only=True))
                for row in filas[1:]:
                    if not row or not any(row): continue
                    resultado.insert(0, {
                        "fecha": str(row[0]),
                        "equipo": str(row[1]),
                        "operador": str(row[2]),
                        "tipo_limpieza": str(row[3]),
                        "hora_inicio": str(row[4]),
                        "hora_final": str(row[5]),
                        "concentracion_1": str(row[6]),
                        "concentracion_2": str(row[7]),
                        "agua_inicial": row[8],
                        "agua_final": row[9],
                        "consumo_agua": row[10],
                        "turbiedad": str(row[11]),
                        "ph_final": str(row[12]),
                        "observaciones": str(row[13]) if len(row) > 13 else ""
                    })
            wb.close()
        except Exception as e:
            print(f"Error leyendo limpieza UF de Excel: {e}")
            
    return {"data": resultado}

@app.post("/api/limpieza-uf/guardar")
def guardar_limpieza_uf(payload: PayloadLimpiezaUF):
    nombre_archivo = "Bitacora_PTAP.xlsx"
    nombre_hoja = "Limpieza_UF"
    consumo = max(0.0, round(payload.agua_final - payload.agua_inicial, 2))
    
    encabezados = [
        "Fecha", "Equipo", "Operador", "Tipo de limpieza", "Hora Inicio", 
        "Hora final", "Concentración 1", "Concentración 2", "Agua Inicial", 
        "Agua Final", "Consumo", "Turbiedad", "pH Final", "Observaciones"
    ]
    
    try:
        wb = openpyxl.load_workbook(nombre_archivo) if os.path.exists(nombre_archivo) else openpyxl.Workbook()
        ws = wb[nombre_hoja] if nombre_hoja in wb.sheetnames else wb.create_sheet(title=nombre_hoja)
        
        if ws.max_row == 1 and ws.cell(1, 1).value is None:
            ws.append(encabezados)
            
        ws.append([
            payload.fecha, payload.equipo, payload.operador, payload.tipo_limpieza,
            payload.hora_inicio, payload.hora_final, payload.concentracion_1,
            payload.concentracion_2, payload.agua_inicial, payload.agua_final,
            consumo, payload.turbiedad, payload.ph_final, payload.observaciones
        ])
        wb.save(nombre_archivo)
        wb.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- MÓDULO: PLANES DE ACCIÓN ---

class PayloadPlanAccion(BaseModel):
    fecha: str
    turno: str
    modulo: str
    zona: str
    parametro: str
    valor_registrado: str
    limite_esperado: str
    descripcion_accion: str
    operador: str

@app.get("/planes-accion", response_class=HTMLResponse)
def vista_planes_accion(request: Request):
    return templates.TemplateResponse(request, "planes_accion.html", {
        "request": request,
        "operadores": OPERADORES_PTAP
    })

@app.get("/api/planes-accion/registros")
def consultar_planes_accion(db: Session = Depends(get_db)):
    registros = db.query(models.RegistroPlanAccion).order_by(models.RegistroPlanAccion.id.desc()).all()
    return {"data": registros}

@app.post("/api/planes-accion/guardar")
def guardar_plan_accion(payload: PayloadPlanAccion, db: Session = Depends(get_db)):
    nuevo = models.RegistroPlanAccion(
        fecha=payload.fecha,
        turno=payload.turno,
        modulo=payload.modulo,
        zona=payload.zona,
        parametro=payload.parametro,
        valor_registrado=payload.valor_registrado,
        limite_esperado=payload.limite_esperado,
        descripcion_accion=payload.descripcion_accion,
        operador=payload.operador
    )
    db.add(nuevo)
    db.commit()
    return {"status": "ok", "message": "Plan de acción registrado correctamente."}
