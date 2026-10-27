from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from database import Base

class RegistroPlanCalidad(Base):
    __tablename__ = "plan_calidad_registros"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), index=True)  # Formato AAAA-MM-DD
    turno = Column(String(20), index=True)  # Turno 1, Turno 2, Turno 3
    operador = Column(String(120), index=True)
    zona = Column(String(150), index=True)
    parametro = Column(String(150), index=True)
    valor = Column(String(50))
    resultado = Column(String(30))  # Cumple, FUERA DE RANGO
    limite = Column(String(100))
    creado_en = Column(DateTime, default=datetime.now)

class ExcepcionPlanCalidad(Base):
    __tablename__ = "plan_calidad_excepciones"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), index=True)
    turno = Column(String(20))
    zona = Column(String(150))
    parametro = Column(String(150))
    estado = Column(String(50))  # Equipo fuera de servicio, No correspondia
    observacion = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.now)