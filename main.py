from fastapi import FastAPI, Depends, HTTPException, Query, Request, UploadFile, File, Form, Header
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Optional, Any
from collections import defaultdict
import openpyxl
import os
import json
import hashlib
import hmac
import secrets
import subprocess
import tempfile
import zipfile
import io
import math
from pathlib import Path

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
MAESTRA_PLAN_CALIDAD = [('Entrada Agua Potable', 'Agua Fuente (Río)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Agua Fuente (Pozo 1)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Agua Fuente (Pozo 2)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Agua Fuente (Pozo 3)', 'Turno', 'Todos', 'Todos', '%', 'numero'), ('Entrada Agua Potable', 'Cloro residual (Muestra 1)', 'Turno', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Entrada Agua Potable', 'Cloro residual (Muestra 2)', 'Turno', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Entrada Agua Potable', 'pH', 'Turno', 'Todos', 'Todos', '6,5 - 7,5', 'numero'), ('Entrada Agua Potable', 'Hierro total (Fe)', 'Diario', 'Todos', 'Turno 1', '0 - 0,1', 'numero'), ('Entrada Agua Potable', 'Evaluación Sensorial', 'Diario', 'Todos', 'Todos', 'Pasa / No pasa', 'sensorial'), ('Entrada Agua Potable', 'Turbiedad (Lab)', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Entrada Agua Potable', 'Turbiedad (Linea)', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Entrada Agua Potable', 'Sólidos disueltos totales (TDS)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Entrada Agua Potable', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Entrada Agua Potable', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Entrada Agua Potable', 'Dureza Total', 'Semanal', 'Miércoles', 'Turno 1', '0 - 100', 'numero'), ('Entrada Agua Potable', 'Cloruros', 'Semanal', 'Miércoles', 'Turno 1', '0 - 250', 'numero'), ('Entrada Agua Potable', 'Diferencial de Presión Filtro 1', 'Semanal', 'Miércoles', 'Turno 1', '0 - 10', 'numero'), ('Entrada Agua Potable', 'Diferencial de Presión Filtro 2', 'Semanal', 'Miércoles', 'Turno 1', '0 - 10', 'numero'), ('Entrada Agua Potable', 'Sulfatos', 'Semanal', 'Martes', 'Turno 1', '0 - 50', 'numero'), ('Entrada Agua Potable', 'Aluminio (Al)', 'Semanal', 'Martes', 'Turno 1', '0 - 0,1', 'numero'), ('Entrada Agua Potable', 'Alcalinidad Total', 'Semanal', 'Martes', 'Turno 1', '0 - 90', 'numero'), ('Entrada Agua Potable', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Entrada Agua Potable', 'COT (Pozo 1)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Pozo 2)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Pozo 3)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Rio)', '2 veces al mes', 'Jueves', 'Turno 2', '0 - 10', 'numero'), ('Entrada Agua Potable', 'COT (Entrada agua potable)', 'Semanal', 'Miércoles', 'Turno 2', '0 - 5', 'numero'), ('Agua potable para Servicios Generales', 'Cloro residual', 'Diario', 'Todos', 'Turno 1', '0,5 - 2', 'numero'), ('Casino principal', 'Cloro residual', 'Semanal', 'Jueves', 'Turno 1', '0,5 - 2', 'numero'), ('Baño envasado', 'Cloro residual', 'Semanal', 'Jueves', 'Turno 1', '0,5 - 2', 'numero'), ('Casino Postobón', 'Cloro residual', 'Semanal', 'Jueves', 'Turno 1', '0,5 - 2', 'numero'), ('Agua Suavizada', 'Dureza Total', 'Diario', 'Todos', 'Turno 1', '0 - 5', 'numero'), ('Agua Suavizada', 'pH', 'Diario', 'Todos', 'Turno 1', '6,5 - 8', 'numero'), ('Agua Suavizada', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Agua Suavizada', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Agua Suavizada', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Agua Suavizada', 'Solidos disueltos totales (TDS)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Almacenamiento de agua potable para proceso', 'Cloro residual', 'Diario', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 1 agua Cervezera', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 2 agua Cervezera', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 1 de agua de Servicios', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Ultrafiltración 2 de agua de Servicios', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Tanque de almacenamiento PTAP cervecera', 'Cloro residual', 'Diario', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Tanque de almacenamiento PTAP cervecera', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 3', 'numero'), ('Tanque de almacenamiento PATP Servicios', 'Cloro residual', 'Diario', 'Todos', 'Todos', '0,5 - 2', 'numero'), ('Tanque de almacenamiento PATP Servicios', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 3', 'numero'), ('Filtracion por carbon agua cervecera', 'Cloro residual F C1', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua cervecera', 'Cloro residual F C2', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua cervecera', 'Cloro residual F C3', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua de servicios', 'Cloro residual F C1', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua de servicios', 'Cloro residual F C2', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Filtracion por carbon agua de servicios', 'Cloro residual F C3', 'Semanal', 'Martes', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua cervecera', 'Cloro residual (Lab)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua cervecera', 'Cloro residual (Linea)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua cervecera', 'Concentración dioxido de cloro (Lab)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Salida tren filtros agua cervecera', 'Concentración dioxido de cloro (Linea)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Salida tren filtros agua cervecera', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 2', 'numero'), ('Salida tren filtros agua de servicios', 'Cloro residual (Lab)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua de servicios', 'Cloro residual (Linea)', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Salida tren filtros agua de servicios', 'Concentración dioxido de cloro (Lab)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Salida tren filtros agua de servicios', 'Concentración dioxido de cloro (Linea)', 'Diario', 'Todos', 'Turno 1', '0 - 0,4', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'pH (Muestra 1)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'pH (Muestra 2)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Cloro residual', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Evaluación Sensorial', 'Diario', 'Todos', 'Todos', 'Pasa / No pasa', 'sensorial'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Intensidad lampara UV 1', 'Diario', 'Todos', 'Todos', '0 - 25', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Intensidad lampara UV 2', 'Diario', 'Todos', 'Todos', '0 - 25', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Dureza Total', 'Semanal', 'Miércoles', 'Turno 1', '0 - 90', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Cloruros', 'Semanal', 'Miércoles', 'Turno 1', '0 - 70', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Solidos disueltos totales', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Sulfatos', 'Semanal', 'Martes', 'Turno 1', '0 - 50', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Alcalinidad Total', 'Semanal', 'Martes', 'Turno 1', '0 - 90', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Aluminio (Al)', 'Semanal', 'Martes', 'Turno 1', '0 - 0,1', 'numero'), ('Tratamiento con luz Ultravioleta agua cervecera', 'Dióxido de Cloro', 'Diario', 'Todos', 'Todos', '0 - 0,4', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'pH (Muestra 1)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'pH (Muestra 2)', 'Diario', 'Todos', 'Todos', '6,5 - 7,2', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Cloro residual', 'Diario', 'Todos', 'Turno 1', '< 0,10', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Turbiedad', 'Diario', 'Todos', 'Turno 1', '0 - 0,5', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Evaluación Sensorial', 'Diario', 'Todos', 'Todos', 'Pasa / No pasa', 'sensorial'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Intensidad lampara UV 1', 'Diario', 'Todos', 'Todos', '0 - 25', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Color', 'Semanal', 'Miércoles', 'Turno 1', '0 - 15', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Hierro total (Fe)', 'Semanal', 'Miércoles', 'Turno 1', '0 - 0,1', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Dureza Total', 'Semanal', 'Miércoles', 'Turno 1', '< 90 ppm', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Cloruros', 'Semanal', 'Miércoles', 'Turno 1', '0 - 70', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Solidos disueltos totales', 'Semanal', 'Miércoles', 'Turno 1', '0 - 500', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Conductividad', 'Semanal', 'Miércoles', 'Turno 1', '0 - 746', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Sulfatos', 'Semanal', 'Martes', 'Turno 1', '0 - 50', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Manganeso', 'Semanal', 'Martes', 'Turno 1', '0 - 0,05', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Alcalinidad Total', 'Semanal', 'Martes', 'Turno 1', '0 - 90', 'numero'), ('Tratamiento con luz Ultravioleta agua de servicios', 'Aluminio (Al)', 'Semanal', 'Martes', 'Turno 1', '0 - 0,1', 'numero'), ('Cuarto generación dióxido de cloro', 'Nivel de los tanques buffer', 'Diario', 'Todos', 'Todos', 'Cumple / No cumple', 'estado'), ('Salida tren filtros agua de servicios', 'COT', 'Diario', 'Todos', 'Turno 2', '0 - 2', 'numero')]


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
    rows = db.query(models.RegistroContador24h).order_by(models.RegistroContador24h.fecha.desc(), models.RegistroContador24h.id.desc()).all()
    return {"data": [{"id": r.id, "fecha": r.fecha, "operador": r.operador,
                      "lecturas": json.loads(r.lecturas_json)} for r in rows]}

@app.post("/api/contadores/guardar")
def guardar_contadores_24h(payload: PayloadContadores24h, db: Session = Depends(get_db)):
    if db.query(models.RegistroContador24h).filter_by(fecha=payload.fecha).first():
        raise HTTPException(409, "Ya existe un registro para esta fecha. Modifíquelo en lugar de duplicarlo.")
    row = models.RegistroContador24h(fecha=payload.fecha, operador=payload.operador,
                                    lecturas_json=json.dumps(payload.lecturas, ensure_ascii=False))
    db.add(row); db.commit()
    return {"status": "ok", "id": row.id}

@app.put("/api/contadores/actualizar/{registro_id}")
def actualizar_contadores(registro_id: int, payload: PayloadContadores24h, db: Session = Depends(get_db)):
    row = db.get(models.RegistroContador24h, registro_id)
    if not row: raise HTTPException(404, "Registro no encontrado")
    row.fecha, row.operador = payload.fecha, payload.operador
    row.lecturas_json = json.dumps(payload.lecturas, ensure_ascii=False)
    db.commit(); return {"status": "ok"}

@app.delete("/api/contadores/eliminar/{registro_id}")
def eliminar_contadores(registro_id: int, db: Session = Depends(get_db)):
    row = db.get(models.RegistroContador24h, registro_id)
    if not row: raise HTTPException(404, "Registro no encontrado")
    db.delete(row); db.commit(); return {"status": "ok"}


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
def consultar_registros_limpieza_uf(db: Session = Depends(get_db)):
    rows = db.query(models.RegistroLimpiezaUF).order_by(models.RegistroLimpiezaUF.fecha.desc(), models.RegistroLimpiezaUF.id.desc()).all()
    return {"data": rows}

@app.post("/api/limpieza-uf/guardar")
def guardar_limpieza_uf(payload: PayloadLimpiezaUF, db: Session = Depends(get_db)):
    consumo = round(payload.agua_final - payload.agua_inicial, 2)
    if consumo < 0: raise HTTPException(422, "El contador final no puede ser inferior al inicial")
    row = models.RegistroLimpiezaUF(**payload.dict(), consumo_agua=consumo)
    db.add(row); db.commit(); return {"status": "ok", "id": row.id}

@app.put("/api/limpieza-uf/actualizar/{registro_id}")
def actualizar_uf(registro_id: int, payload: PayloadLimpiezaUF, db: Session = Depends(get_db)):
    row = db.get(models.RegistroLimpiezaUF, registro_id)
    if not row: raise HTTPException(404, "Registro no encontrado")
    for k,v in payload.dict().items(): setattr(row,k,v)
    row.consumo_agua = round(payload.agua_final - payload.agua_inicial,2)
    if row.consumo_agua < 0: raise HTTPException(422, "Contadores inconsistentes")
    db.commit(); return {"status": "ok"}

@app.delete("/api/limpieza-uf/eliminar/{registro_id}")
def eliminar_uf(registro_id: int, db: Session = Depends(get_db)):
    row = db.get(models.RegistroLimpiezaUF, registro_id)
    if not row: raise HTTPException(404, "Registro no encontrado")
    db.delete(row); db.commit(); return {"status": "ok"}


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


# ============================================================
# IMPORTACIÓN HISTÓRICA DESDE NAVEGADOR (ADMINISTRACIÓN)
# Se exige un secreto configurado en Render; sin él no funciona.
# La simulación no escribe en PostgreSQL. La carga exige una
# confirmación y una vista previa del MISMO archivo.
# ============================================================
_IMPORT_ROOT = Path(__file__).resolve().parent
_IMPORT_MAX_BYTES = 12 * 1024 * 1024


def _import_auth(request: Request, clave: str):
    expected = os.environ.get("PTAP_IMPORT_ADMIN_KEY", "")
    if len(expected) < 24:
        raise HTTPException(503, "Configure PTAP_IMPORT_ADMIN_KEY (mínimo 24 caracteres) en Render")
    if not hmac.compare_digest(clave or "", expected):
        raise HTTPException(403, "Clave de importación incorrecta")
    # Las peticiones con escritura deben proceder del mismo sitio.
    origin = request.headers.get("origin", "")
    if not origin:
        raise HTTPException(403, "Origen de solicitud no disponible")
    from urllib.parse import urlparse
    u = urlparse(origin)
    if u.scheme not in ("https", "http") or u.netloc != request.url.netloc:
        raise HTTPException(403, "Origen no autorizado")
    return expected


@app.get("/importar-registros", response_class=HTMLResponse)
def vista_importar_registros(request: Request):
    return templates.TemplateResponse(request, "importar_registros.html", {"request": request})


@app.post("/api/importacion/analizar")
async def analizar_importacion(request: Request, archivo: UploadFile = File(...),
                              clave: str = Form(...), aplicar: str = Form("no"),
                              confirmacion: str = Form(""), firma: str = Form("")):
    secret = _import_auth(request, clave)
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Seleccione un archivo Excel .xlsx")
    data = await archivo.read(_IMPORT_MAX_BYTES + 1)
    if len(data) > _IMPORT_MAX_BYTES:
        raise HTTPException(413, "Archivo demasiado grande (máximo 12 MB)")
    if not zipfile.is_zipfile(__import__('io').BytesIO(data)):
        raise HTTPException(400, "El archivo no es un XLSX válido")
    with zipfile.ZipFile(__import__('io').BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist()) > 45 * 1024 * 1024:
            raise HTTPException(413, "Contenido XLSX descomprimido demasiado grande")
    digest = hashlib.sha256(data).hexdigest()
    expected_sig = hmac.new(secret.encode(), digest.encode(), hashlib.sha256).hexdigest()
    write = aplicar == "si"
    if write and (confirmacion != "IMPORTAR" or not hmac.compare_digest(firma, expected_sig)):
        raise HTTPException(400, "Primero analice este mismo archivo y confirme IMPORTAR")
    with tempfile.TemporaryDirectory(prefix="ptap-import-") as td:
        xlsx = Path(td) / "fuente.xlsx"
        report = Path(td) / "reporte.txt"
        xlsx.write_bytes(data)
        env = os.environ.copy()
        env["PTAP_IMPORT_SOURCE"] = str(xlsx)
        env["PTAP_IMPORT_REPORT"] = str(report)
        try:
            run = subprocess.run(
                [__import__('sys').executable, str(_IMPORT_ROOT / "importar_noviembre.py")]
                + (["--aplicar"] if write else []),
                cwd=str(_IMPORT_ROOT), env=env, capture_output=True,
                text=True, timeout=110,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "La importación superó el tiempo permitido; revise el historial antes de reintentar")
        if run.returncode != 0:
            # No exponer rastros internos ni credenciales en respuestas públicas.
            raise HTTPException(500, "No se completó la operación. Consulte los Logs de Render; no repita la carga sin verificar.")
        content = report.read_text(encoding="utf-8") if report.exists() else run.stdout
    return {"modo": "IMPORTACIÓN REAL" if write else "SIMULACIÓN SIN ESCRITURA",
            "reporte": content, "firma": "" if write else expected_sig,
            "hash_archivo": digest}


# ==========================================================
# MÓDULOS COMPLEMENTARIOS - PostgreSQL
# Módulos nuevos: no se altera ni borra ninguna tabla anterior.
# ==========================================================
MODULOS_COMPLEMENTARIOS = {
 "laboratorio": {"titulo":"Verificación de Equipos de Laboratorio", "campos":[
  ["instrumento","Instrumento","select","pH-metro|Conductivímetro|Turbidímetro"],
  ["patron","Patrón de verificación","text"], ["lectura","Lectura obtenida","text"],
  ["pendiente","Pendiente / slope","text"], ["resultado","Resultado","select","Cumple|No cumple|Pendiente"],
  ["observaciones","Observaciones","textarea"]]},
 "inventario": {"titulo":"Inventario de Químicos", "campos":[
  ["quimico","Producto químico","text"], ["movimiento","Movimiento","select","Saldo inicial|Entrada|Consumo"],
  ["cantidad","Cantidad","number"], ["unidad","Unidad","text"],
  ["stock_minimo","Stock mínimo","number"], ["observaciones","Observaciones","textarea"]]},
 "cip": {"titulo":"Registro CIP", "campos":[
  ["linea","Línea","select","Cervecera AWT|Servicios SW1|Envasado"],
  ["hora_inicio","Hora inicio","time"], ["hora_final","Hora final","time"],
  ["ph_final","pH enjuague final","text"], ["responsables","Responsables (varios)","text"],
  ["principal_mezclado","Principal - Mezclado inicial (%)","number"],
  ["trimeta_mezclado","Trimeta - Mezclado inicial (%)","number"],
  ["principal_circulacion","Principal - Circulación (%)","number"],
  ["trimeta_circulacion","Trimeta - Circulación (%)","number"],
  ["principal_etapa3","Principal - Etapa 3 (%)","number"],
  ["trimeta_etapa3","Trimeta - Etapa 3 (%)","number"],
  ["principal_final","Principal - Etapa final (%)","number"],
  ["trimeta_final","Trimeta - Etapa final (%)","number"],
  ["observaciones","Observaciones","textarea"]]},
 "muestreo-compuesto": {"titulo":"Muestreo Compuesto PTAP (Laboratorio Externo)", "campos":[
  ["laboratorio","Laboratorio externo","text"], ["informe","Número de informe","text"],
  ["punto","Punto de muestreo","select","Entrada Agua Potable|Tratamiento UV Agua Cervecera|Tratamiento UV Agua Servicios"],
  ["parametro","Parámetro","text"], ["resultado","Resultado","text"],
  ["unidad","Unidad","text"], ["especificacion","Especificación","text"],
  ["cumplimiento","Cumplimiento","select","Cumple|No cumple|Pendiente"],
  ["observaciones","Observaciones","textarea"]]},
 "bitacora-nueva": {"titulo":"Bitácora Operacional (PostgreSQL)", "campos":[
  ["reporte","Actividades y novedades","textarea"],
  ["requiere_atencion","Requiere seguimiento","select","No|Sí"],
  ["estado","Estado","select","Pendiente|En seguimiento|Solucionada"],
  ["observaciones","Observaciones de seguimiento","textarea"]]},
}

class PayloadRegistroOperacional(BaseModel):
    fecha: str
    turno: str = ""
    operador: str = ""
    equipo: str = ""
    datos: dict[str, Any]

def _clave_operacion(request: Request):
    expected = os.environ.get("PTAP_IMPORT_ADMIN_KEY", "")
    supplied = request.headers.get("x-ptap-admin-key", "")
    if len(expected) < 24:
        raise HTTPException(503, "Configure PTAP_IMPORT_ADMIN_KEY en Render")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(403, "Clave de administración incorrecta")
    origin = request.headers.get("origin")
    from urllib.parse import urlparse
    if not origin or urlparse(origin).netloc != request.url.netloc:
        raise HTTPException(403, "Origen no autorizado")

def _validar_operacional(modulo, payload):
    if modulo not in MODULOS_COMPLEMENTARIOS:
        raise HTTPException(404, "Módulo no encontrado")
    try:
        date.fromisoformat(payload.fecha)
    except ValueError:
        raise HTTPException(422, "Fecha inválida")
    permitidos = {c[0] for c in MODULOS_COMPLEMENTARIOS[modulo]["campos"]}
    if not isinstance(payload.datos, dict) or set(payload.datos) - permitidos:
        raise HTTPException(422, "Campos no admitidos")
    if len(json.dumps(payload.datos, ensure_ascii=False)) > 25000:
        raise HTTPException(422, "Registro demasiado grande")
    for campo in MODULOS_COMPLEMENTARIOS[modulo]["campos"]:
        v = payload.datos.get(campo[0])
        if v is not None and not isinstance(v, (str, int, float, bool)):
            raise HTTPException(422, "Valor inválido: " + campo[0])
        if campo[2] == "select" and v not in (None, "") and str(v) not in campo[3].split("|"):
            raise HTTPException(422, "Opción inválida: " + campo[0])
        if campo[2] == "number" and v not in (None, ""):
            try:
                n = float(v)
                if not (-1e12 < n < 1e12): raise ValueError()
                if modulo == "inventario" and campo[0] in ("cantidad", "stock_minimo") and n < 0: raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(422, "Número inválido: " + campo[0])
    if modulo == "inventario":
        if not str(payload.datos.get("quimico") or "").strip():
            raise HTTPException(422, "Indique el producto químico")
        if payload.datos.get("movimiento") not in ("Saldo inicial", "Entrada", "Consumo"):
            raise HTTPException(422, "Indique el tipo de movimiento")
        if not payload.datos.get("cantidad") or float(payload.datos["cantidad"]) <= 0:
            raise HTTPException(422, "La cantidad debe ser mayor que cero")
    if modulo == "cip":
        inicio, fin = payload.datos.get("hora_inicio"), payload.datos.get("hora_final")
        if inicio and fin:
            try:
                h1=datetime.strptime(inicio, "%H:%M")
                h2=datetime.strptime(fin, "%H:%M")
            except ValueError:
                raise HTTPException(422, "Horas CIP inválidas")
            minutos=int((h2-h1).total_seconds()/60) % 1440
            if minutos == 0:
                raise HTTPException(422, "La duración CIP debe ser mayor que cero")
    if modulo == "muestreo-compuesto" and not payload.datos.get("parametro"):
        raise HTTPException(422, "Indique el parámetro")

def _salida_operacional(r):
    return {"id":r.id,"modulo":r.modulo,"fecha":r.fecha,"turno":r.turno,
            "operador":r.operador,"equipo":r.equipo,"datos":json.loads(r.datos_json),
            "creado_en":r.creado_en.isoformat() if r.creado_en else None}

@app.get("/operacion/{modulo}", response_class=HTMLResponse)
def pagina_operacional(modulo: str, request: Request):
    if modulo not in MODULOS_COMPLEMENTARIOS:
        raise HTTPException(404, "Módulo no encontrado")
    return templates.TemplateResponse(request, "operacion.html", {
        "request":request,"modulo":modulo,"config":MODULOS_COMPLEMENTARIOS[modulo],
        "operadores":OPERADORES_PTAP})

@app.get("/api/operacion/{modulo}")
def listar_operacional(modulo: str, desde: Optional[str] = None, hasta: Optional[str] = None,
                       db: Session = Depends(get_db)):
    if modulo not in MODULOS_COMPLEMENTARIOS: raise HTTPException(404)
    q = db.query(models.RegistroOperacional).filter_by(modulo=modulo)
    if desde: q=q.filter(models.RegistroOperacional.fecha >= desde)
    if hasta: q=q.filter(models.RegistroOperacional.fecha <= hasta)
    registros=q.order_by(models.RegistroOperacional.fecha.desc(), models.RegistroOperacional.id.desc()).limit(1500).all()
    return {"data":[_salida_operacional(r) for r in registros]}

def _validar_saldo_inventario(db: Session, payload: PayloadRegistroOperacional, excluir_id=None):
    if not payload.datos.get("quimico"):
        return
    producto = str(payload.datos["quimico"]).strip().casefold()
    movimientos = db.query(models.RegistroOperacional).filter_by(modulo="inventario").all()
    saldo = 0.0
    for r in movimientos:
        if excluir_id is not None and r.id == excluir_id:
            continue
        d = json.loads(r.datos_json)
        if str(d.get("quimico") or "").strip().casefold() != producto:
            continue
        cantidad = float(d.get("cantidad") or 0)
        saldo += -cantidad if d.get("movimiento") == "Consumo" else cantidad
    cantidad_nueva = float(payload.datos.get("cantidad") or 0)
    saldo += -cantidad_nueva if payload.datos.get("movimiento") == "Consumo" else cantidad_nueva
    if saldo < -1e-8:
        raise HTTPException(409, "Movimiento rechazado: dejaría existencias negativas")

@app.post("/api/operacion/{modulo}")
def crear_operacional(modulo: str, payload: PayloadRegistroOperacional,
                     request: Request, db: Session = Depends(get_db)):
    _clave_operacion(request); _validar_operacional(modulo,payload)
    if modulo == "inventario": _validar_saldo_inventario(db, payload)
    r=models.RegistroOperacional(modulo=modulo,fecha=payload.fecha,turno=payload.turno,
       operador=payload.operador,equipo=payload.equipo,datos_json=json.dumps(payload.datos,ensure_ascii=False))
    db.add(r); db.commit(); db.refresh(r)
    return {"status":"ok","id":r.id}

@app.put("/api/operacion/{modulo}/{registro_id}")
def modificar_operacional(modulo: str, registro_id: int, payload: PayloadRegistroOperacional,
                         request: Request, db: Session = Depends(get_db)):
    _clave_operacion(request); _validar_operacional(modulo,payload)
    r=db.query(models.RegistroOperacional).filter_by(id=registro_id,modulo=modulo).first()
    if not r: raise HTTPException(404,"Registro no encontrado")
    if modulo == "inventario": _validar_saldo_inventario(db, payload, excluir_id=registro_id)
    r.fecha=payload.fecha; r.turno=payload.turno; r.operador=payload.operador
    r.equipo=payload.equipo; r.datos_json=json.dumps(payload.datos,ensure_ascii=False)
    db.commit(); return {"status":"ok"}

@app.delete("/api/operacion/{modulo}/{registro_id}")
def borrar_operacional(modulo: str, registro_id: int, request: Request,
                       db: Session = Depends(get_db)):
    _clave_operacion(request)
    if modulo not in MODULOS_COMPLEMENTARIOS: raise HTTPException(404)
    r=db.query(models.RegistroOperacional).filter_by(id=registro_id,modulo=modulo).first()
    if not r: raise HTTPException(404,"Registro no encontrado")
    db.delete(r); db.commit(); return {"status":"eliminado"}

@app.get("/api/inventario/saldos")
def saldos_quimicos(db: Session = Depends(get_db)):
    rows=db.query(models.RegistroOperacional).filter_by(modulo="inventario").order_by(models.RegistroOperacional.fecha,models.RegistroOperacional.id).all()
    saldos={}
    for r in rows:
        d=json.loads(r.datos_json); producto=(d.get("quimico") or "").strip()
        if not producto: continue
        estado=saldos.setdefault(producto,{"quimico":producto,"saldo":0,"unidad":d.get("unidad") or "","minimo":0})
        cantidad=float(d.get("cantidad") or 0)
        estado["saldo"]+= -cantidad if d.get("movimiento")=="Consumo" else cantidad
        if d.get("stock_minimo") not in (None,""): estado["minimo"]=float(d["stock_minimo"])
        estado["alerta"]=estado["saldo"] < estado["minimo"]
    return {"data":list(saldos.values())}


@app.get("/api/reportes/plan-calidad.pdf")
def reporte_diario_plan_calidad(fecha: str, request: Request, db: Session = Depends(get_db)):
    """PDF imprimible: datos efectivamente registrados, separados por turno."""
    _clave_operacion(request)
    try:
        date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(422, "Fecha inválida")
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    rows = db.query(models.RegistroPlanCalidad).filter_by(fecha=fecha).order_by(
        models.RegistroPlanCalidad.turno, models.RegistroPlanCalidad.zona,
        models.RegistroPlanCalidad.parametro).all()
    output=io.BytesIO()
    doc=SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=13*mm,
                          leftMargin=13*mm, topMargin=13*mm, bottomMargin=13*mm)
    styles=getSampleStyleSheet()
    story=[Paragraph("PTAP | PLAN DE CALIDAD - REGISTRO DIARIO",styles["Title"]),
           Paragraph("Fecha: " + fecha + " | Registros almacenados: " + str(len(rows)),styles["Normal"]),Spacer(1,8)]
    for turno in ("Turno 1", "Turno 2", "Turno 3"):
        sub=[r for r in rows if r.turno == turno]
        story.append(Paragraph(turno + " - " + str(len(sub)) + " mediciones",styles["Heading2"]))
        data=[["Zona / Punto", "Parámetro", "Valor", "Resultado", "Límite", "Operador"]]
        for r in sub:
            def clean(x,n=58):
                return (str(x or "")[:n]).replace("&","&amp;").replace("<","&lt;")
            data.append([Paragraph(clean(r.zona,65),styles["BodyText"]),
                         Paragraph(clean(r.parametro,65),styles["BodyText"]),
                         clean(r.valor,22),clean(r.resultado,22),clean(r.limite,22),
                         Paragraph(clean(r.operador,38),styles["BodyText"])])
        if not sub: data.append(["Sin mediciones registradas", "", "", "", "", ""])
        table=Table(data,colWidths=[66*mm,67*mm,27*mm,32*mm,30*mm,48*mm],repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#102e52")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTSIZE",(0,0),(-1,-1),8),
            ("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#ccd6e0")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f2f6fb")]),
            ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story.append(table);story.append(Spacer(1,10))
    doc.build(story)
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="PTAP_plan_calidad_'+fecha+'.pdf"',
        "Cache-Control":"no-store"})


@app.get("/reportes/plan-calidad", response_class=HTMLResponse)
def pantalla_reporte_diario():
    return HTMLResponse("""<!doctype html><html lang=es><meta charset=utf-8><title>Impresión diaria PTAP</title>
    <style>body{font:16px Segoe UI,Arial;background:#f4f7fb;color:#17304f;max-width:640px;margin:6vh auto;padding:20px}main{background:white;padding:28px;border-radius:14px}input,button{display:block;width:100%;padding:12px;margin:10px 0;box-sizing:border-box}button{background:#124e86;color:white;border:0;border-radius:8px;cursor:pointer}</style>
    <main><a href=/plan-calidad>← Volver al Plan de Calidad</a><h1>Impresión diaria</h1>
    <p>Genera un PDF con los datos realmente almacenados para los tres turnos de una fecha.</p>
    <label>Fecha<input type=date id=fecha required></label><label>Clave de administración<input type=password id=clave required></label>
    <button onclick=generar()>Generar PDF</button><p id=estado role=status></p></main>
    <script>document.getElementById('fecha').value=new Date().toLocaleDateString('en-CA');
    async function generar(){const f=document.getElementById('fecha').value,k=document.getElementById('clave').value;
    if(!f||!k){document.getElementById('estado').textContent='Complete fecha y clave';return}
    try{let r=await fetch('/api/reportes/plan-calidad.pdf?fecha='+encodeURIComponent(f),{headers:{'x-ptap-admin-key':k}});
    if(!r.ok){let j=await r.json();throw Error(j.detail||'No se pudo generar el PDF')}
    const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='PTAP_plan_calidad_'+f+'.pdf';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
    document.getElementById('estado').textContent='PDF generado';}catch(e){document.getElementById('estado').textContent=e.message}}</script></html>""")
