from sqlalchemy import Column, Integer, String, Float, DateTime, Text, UniqueConstraint
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
    
class RegistroLimpiezaFiltro(Base):
    __tablename__ = "limpieza_filtros_registros"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), index=True)
    equipo = Column(String(50), index=True) 
    operador = Column(String(120))
    tipo_limpieza = Column(String(100)) 
    hora_muestra_antes = Column(String(20), nullable=True)
    hora_inicio_est = Column(String(20), nullable=True)
    hora_final_est = Column(String(20), nullable=True)
    hora_muestra_despues = Column(String(20), nullable=True)
    temperatura = Column(String(20), nullable=True)
    perdida_carbon = Column(String(10), default="No", nullable=True)
    agua_inicial = Column(Float, nullable=True)
    agua_final = Column(Float, nullable=True)
    consumo_agua = Column(Float, nullable=True)
    cloro = Column(String(50), nullable=True)
    turbidez = Column(String(50), nullable=True)
    creado_en = Column(DateTime, default=datetime.now)

class RegistroPlanAccion(Base):
    __tablename__ = "planes_accion_registros"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String(10), index=True)
    turno = Column(String(20), index=True)
    modulo = Column(String(50), index=True)  # Ej. Plan de Calidad, Limpieza Filtros, etc.
    zona = Column(String(150), index=True)
    parametro = Column(String(150), index=True)
    valor_registrado = Column(String(50))
    limite_esperado = Column(String(100))
    descripcion_accion = Column(Text)
    operador = Column(String(120), index=True)
    creado_en = Column(DateTime, default=datetime.now)


class RegistroContador24h(Base):
    __tablename__ = "contadores_24h_registros"
    id = Column(Integer, primary_key=True)
    fecha = Column(String(10), index=True, nullable=False)
    operador = Column(String(120), default="")
    lecturas_json = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=datetime.now)

class RegistroLimpiezaUF(Base):
    __tablename__ = "limpieza_uf_registros"
    id = Column(Integer, primary_key=True)
    fecha = Column(String(10), index=True, nullable=False)
    equipo = Column(String(50), index=True)
    operador = Column(String(120))
    tipo_limpieza = Column(String(100))
    hora_inicio = Column(String(20))
    hora_final = Column(String(20))
    concentracion_1 = Column(String(50))
    concentracion_2 = Column(String(50))
    agua_inicial = Column(Float)
    agua_final = Column(Float)
    consumo_agua = Column(Float)
    turbiedad = Column(String(50))
    ph_final = Column(String(50))
    observaciones = Column(Text)
    creado_en = Column(DateTime, default=datetime.now)

class RegistroImportacionOrigen(Base):
    __tablename__ = "ptap_importaciones_origen"
    id = Column(Integer, primary_key=True)
    clave = Column(String(180), unique=True, nullable=False, index=True)
    modulo = Column(String(60), nullable=False)
    registro_id = Column(Integer, nullable=False)
    creado_en = Column(DateTime, default=datetime.now)


# Registros independientes de nuevos módulos. No modifica tablas históricas.
class RegistroOperacional(Base):
    __tablename__ = "ptap_registros_operacionales"
    id = Column(Integer, primary_key=True)
    modulo = Column(String(50), nullable=False, index=True)
    fecha = Column(String(10), nullable=False, index=True)
    turno = Column(String(20), nullable=True)
    operador = Column(String(150), nullable=True)
    equipo = Column(String(150), nullable=True)
    datos_json = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=datetime.now)
    actualizado_en = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class VerificacionLaboratorio(Base):
    __tablename__ = "ptap_verificaciones_laboratorio"
    id = Column(Integer, primary_key=True)
    instrumento = Column(String(30), nullable=False)
    fecha = Column(String(10), nullable=False)
    porcentaje = Column(Float, nullable=True)
    pendiente = Column(Float, nullable=False)
    lectura_patron = Column(Float, nullable=True)
    operador = Column(String(150), nullable=False)
    observaciones = Column(Text, nullable=True)
    resultado = Column(String(20), nullable=False)
    __table_args__ = (UniqueConstraint('instrumento', 'fecha', name='uq_lab_instrumento_fecha'),)

class QuimicoProducto(Base):
    __tablename__ = 'inv_quimicos_productos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String(140), nullable=False)
    sap = Column(String(40), default='')
    unidad = Column(String(12), default='kg')
    activo = Column(Integer, default=1, nullable=False)

class QuimicoExistencia(Base):
    __tablename__ = 'inv_quimicos_existencias'
    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, nullable=False, index=True)
    fecha = Column(String(10), nullable=False, index=True)
    cantidad = Column(Float, nullable=False)
    operador = Column(String(120), default='')
    observaciones = Column(Text, default='')
    inicial = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint('producto_id','fecha',name='uq_inv_quimico_fecha'),)

class QuimicoEntrada(Base):
    __tablename__ = 'inv_quimicos_entradas'
    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, nullable=False, index=True)
    fecha = Column(String(10), nullable=False, index=True)
    cantidad = Column(Float, nullable=False)
    operador = Column(String(120), default='')
    observaciones = Column(Text, default='')
