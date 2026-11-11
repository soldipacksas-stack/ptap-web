from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import date, timedelta
from math import isfinite
from typing import Optional
from database import get_db
from models import QuimicoProducto as Producto, QuimicoExistencia as Existencia, QuimicoEntrada as Entrada

router = APIRouter()
DEFAULTS = [('Ácido clorhídrico','1521393'),('Soda cáustica','1521396'),('Hipoclorito de sodio','1521374'),('Principal','1521364'),('Trimeta CD','1521210'),('Ácido cítrico','')]

def setup(templates, operators, authorize):
    def auth(request): authorize(request)
    def valid_date(s):
        try: return date.fromisoformat(s)
        except (ValueError,TypeError): raise HTTPException(422,'Fecha inválida')
    def positive(v,zero=True):
        if not isfinite(v) or v < 0 or (not zero and v==0): raise HTTPException(422,'Cantidad inválida')
    def product(db,pid):
        p=db.get(Producto,pid)
        if not p: raise HTTPException(404,'Producto no encontrado')
        return p
    def check_operator(s):
        if s not in operators: raise HTTPException(422,'Seleccione un operador válido')
    def seed(db):
        if not db.query(Producto).first():
            for n,s in DEFAULTS: db.add(Producto(nombre=n,sap=s,unidad='kg',activo=1))
            db.commit()
    def calc(db,pid):
        xs=db.query(Existencia).filter_by(producto_id=pid).order_by(Existencia.fecha).all()
        ins=db.query(Entrada).filter_by(producto_id=pid).all()
        bydate={}
        for e in ins: bydate[e.fecha]=bydate.get(e.fecha,0)+e.cantidad
        # Cada par de mediciones consecutivas debe ser de días consecutivos.
        for a,b in zip(xs,xs[1:]):
            if (date.fromisoformat(b.fecha)-date.fromisoformat(a.fecha)).days != 1: continue
            entradas=sum(v for k,v in bydate.items() if a.fecha<k<=b.fecha)
            if a.cantidad+entradas-b.cantidad < -1e-7:
                raise HTTPException(409,f'Inconsistencia en {b.fecha}: las existencias superan el saldo anterior más las entradas')
    class ProductoIn(BaseModel):
        nombre:str
        sap:str=''
        activo:bool=True
    class ExistenciaIn(BaseModel):
        fecha:str
        producto_id:int
        cantidad:float
        operador:str
        observaciones:str=''
        inicial:bool=False
    class EntradaIn(BaseModel):
        fecha:str
        producto_id:int
        cantidad:float
        operador:str
        observaciones:str=''

    @router.get('/inventario-quimicos',response_class=HTMLResponse)
    def page(request:Request):
        return templates.TemplateResponse(request,'inventario_quimicos.html',{'request':request,'operadores':operators})

    @router.get('/api/inv-quimicos')
    def listing(desde:str,hasta:str,db:Session=Depends(get_db)):
        a,b=valid_date(desde),valid_date(hasta)
        if b<a or (b-a).days>370: raise HTTPException(422,'Rango máximo de 371 días')
        seed(db)
        ps=db.query(Producto).order_by(Producto.id).all()
        xs=db.query(Existencia).filter(Existencia.fecha<=hasta).order_by(Existencia.fecha).all()
        es=db.query(Entrada).filter(Entrada.fecha<=hasta).order_by(Entrada.fecha).all()
        products=[dict(id=p.id,nombre=p.nombre,sap=p.sap,unidad=p.unidad,activo=bool(p.activo)) for p in ps]
        exist=[dict(id=x.id,producto_id=x.producto_id,fecha=x.fecha,cantidad=x.cantidad,operador=x.operador,observaciones=x.observaciones,inicial=bool(x.inicial)) for x in xs]
        entradas=[dict(id=e.id,producto_id=e.producto_id,fecha=e.fecha,cantidad=e.cantidad,operador=e.operador,observaciones=e.observaciones) for e in es]
        return {'productos':products,'existencias':exist,'entradas':entradas,'desde':desde,'hasta':hasta}

    @router.post('/api/inv-quimicos/productos')
    def create_product(payload:ProductoIn,request:Request,db:Session=Depends(get_db)):
        auth(request)
        if not payload.nombre.strip() or len(payload.nombre)>140 or len(payload.sap)>40: raise HTTPException(422,'Producto inválido')
        p=Producto(nombre=payload.nombre.strip(),sap=payload.sap.strip(),activo=int(payload.activo),unidad='kg')
        db.add(p);db.commit();return {'id':p.id}
    @router.put('/api/inv-quimicos/productos/{pid}')
    def edit_product(pid:int,payload:ProductoIn,request:Request,db:Session=Depends(get_db)):
        auth(request);p=product(db,pid)
        if not payload.nombre.strip() or len(payload.nombre)>140 or len(payload.sap)>40: raise HTTPException(422,'Producto inválido')
        p.nombre=payload.nombre.strip();p.sap=payload.sap.strip();p.activo=int(payload.activo);db.commit();return {'ok':True}

    @router.post('/api/inv-quimicos/existencias')
    def add_stock(payload:ExistenciaIn,request:Request,db:Session=Depends(get_db)):
        auth(request);valid_date(payload.fecha);positive(payload.cantidad);check_operator(payload.operador);p=product(db,payload.producto_id)
        if not p.activo: raise HTTPException(422,'Producto desactivado')
        if db.query(Existencia).filter_by(producto_id=p.id,fecha=payload.fecha).first(): raise HTTPException(409,'Ya existe registro para esta fecha; use Modificar')
        if payload.inicial and db.query(Existencia).filter_by(producto_id=p.id).first(): raise HTTPException(409,'El inventario inicial ya fue configurado para este producto')
        if not payload.inicial and not db.query(Existencia).filter(Existencia.producto_id==p.id,Existencia.inicial==1,Existencia.fecha<=payload.fecha).first(): raise HTTPException(409,'Configure primero el inventario inicial del producto')
        x=Existencia(**payload.model_dump(exclude={'inicial'}),inicial=int(payload.inicial));db.add(x)
        try: db.flush();calc(db,p.id);db.commit()
        except Exception: db.rollback();raise
        return {'id':x.id}
    @router.put('/api/inv-quimicos/existencias/{rid}')
    def edit_stock(rid:int,payload:ExistenciaIn,request:Request,db:Session=Depends(get_db)):
        auth(request);valid_date(payload.fecha);positive(payload.cantidad);check_operator(payload.operador)
        x=db.get(Existencia,rid)
        if not x: raise HTTPException(404,'Registro no encontrado')
        if x.fecha!=payload.fecha or x.producto_id!=payload.producto_id or bool(x.inicial)!=payload.inicial: raise HTTPException(422,'Fecha, producto y tipo no pueden cambiarse')
        x.cantidad=payload.cantidad;x.operador=payload.operador;x.observaciones=payload.observaciones
        try: db.flush();calc(db,x.producto_id);db.commit()
        except Exception: db.rollback();raise
        return {'ok':True}
    @router.delete('/api/inv-quimicos/existencias/{rid}')
    def delete_stock(rid:int,request:Request,db:Session=Depends(get_db)):
        auth(request);x=db.get(Existencia,rid)
        if not x: raise HTTPException(404,'Registro no encontrado')
        pid=x.producto_id
        if x.inicial and db.query(Existencia).filter(Existencia.producto_id==pid,Existencia.id!=rid).first(): raise HTTPException(409,'No puede eliminar el inventario inicial mientras existan registros posteriores')
        db.delete(x)
        try: db.flush();calc(db,pid);db.commit()
        except Exception: db.rollback();raise
        return {'ok':True}
    @router.post('/api/inv-quimicos/entradas')
    def add_entry(payload:EntradaIn,request:Request,db:Session=Depends(get_db)):
        auth(request);valid_date(payload.fecha);positive(payload.cantidad,False);check_operator(payload.operador);product(db,payload.producto_id)
        if not db.query(Existencia).filter(Existencia.producto_id==payload.producto_id,Existencia.inicial==1,Existencia.fecha<=payload.fecha).first(): raise HTTPException(409,'Configure el inventario inicial antes de registrar entradas')
        e=Entrada(**payload.model_dump());db.add(e)
        try: db.flush();calc(db,e.producto_id);db.commit()
        except Exception: db.rollback();raise
        return {'id':e.id}
    @router.put('/api/inv-quimicos/entradas/{rid}')
    def edit_entry(rid:int,payload:EntradaIn,request:Request,db:Session=Depends(get_db)):
        auth(request);valid_date(payload.fecha);positive(payload.cantidad,False);check_operator(payload.operador)
        e=db.get(Entrada,rid)
        if not e: raise HTTPException(404,'Entrada no encontrada')
        old=e.producto_id
        if not db.query(Existencia).filter(Existencia.producto_id==payload.producto_id,Existencia.inicial==1,Existencia.fecha<=payload.fecha).first(): raise HTTPException(409,'La entrada debe ser posterior o igual al inventario inicial')
        for k,v in payload.model_dump().items():setattr(e,k,v)
        try: db.flush();calc(db,old);calc(db,e.producto_id);db.commit()
        except Exception: db.rollback();raise
        return {'ok':True}
    @router.delete('/api/inv-quimicos/entradas/{rid}')
    def delete_entry(rid:int,request:Request,db:Session=Depends(get_db)):
        auth(request);e=db.get(Entrada,rid)
        if not e: raise HTTPException(404,'Entrada no encontrada')
        pid=e.producto_id;db.delete(e)
        try: db.flush();calc(db,pid);db.commit()
        except Exception: db.rollback();raise
        return {'ok':True}
    return router
