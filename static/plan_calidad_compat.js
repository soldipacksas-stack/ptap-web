/* Adaptador Plan de Calidad: conserva la plantilla original, sin tarjetas V2. */
(function () {
'use strict';
let modoEdicion=false;
const $=id=>document.getElementById(id);
const key=(z,p)=>JSON.stringify([z,p]);
const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function json(res){const data=await res.json().catch(()=>({}));if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));return data;}
function fieldRows(){return [...document.querySelectorAll('#contenedor-parametros .input-medida')];}
function stateOf(inp){return inp.closest('.relative')?.querySelector('.input-estado')?.value||'Resultado';}
function setState(inp,estado){const sel=inp.closest('.relative')?.querySelector('.input-estado');if(!sel)return;sel.value=estado==='Resultado'?'':estado;refreshState(sel);}
function refreshState(sel){
 const card=sel.closest('.relative'),inp=card?.querySelector('.input-medida'),just=card?.querySelector('.pc-justificacion');
 if(!inp)return;
 const estado=sel.value;
 if(estado){if(inp.tagName==='INPUT')inp.type='text';inp.value=estado;inp.readOnly=true;}
 else {if(inp.tagName==='INPUT')inp.type=inp.dataset.originalType||'number';if(['NA','NC','Pendiente'].includes(inp.value))inp.value='';inp.readOnly=false;}
 if(just){just.classList.toggle('hidden',!estado);just.required=!!estado;}
 const plan=document.getElementById(inp.dataset.containerId);if(estado&&plan)plan.classList.add('hidden');
}
function decorate(){
 for(const inp of fieldRows()){
  const card=inp.closest('.relative'),sel=card?.querySelector('.input-estado');if(!sel)continue;
  if(inp.tagName==='INPUT')inp.dataset.originalType=inp.type;
  if(!card.querySelector('.pc-justificacion')){
   const just=document.createElement('input');just.type='text';just.className='pc-justificacion hidden border rounded p-1 text-xs w-full mt-1';just.placeholder='Justificación obligatoria para NA, NC o Pendiente';sel.insertAdjacentElement('afterend',just);
  }
  sel.onchange=()=>refreshState(sel);
  inp.addEventListener('input',()=>{if(!sel.value&&inp.value)try{validarCasillaMedicion(inp)}catch(_){}});
 }
}
const oldRender=window.renderizarCamposDinamicos;
window.renderizarCamposDinamicos=async function(){await oldRender();decorate();};
const oldAbrir=window.abrirModalFormulario;
window.abrirModalFormulario=function(){modoEdicion=false;oldAbrir();$('modalForm').querySelector('h3').textContent='📝 Registrar Mediciones Plan de Calidad';};
function itemData(inp){
 const estado=stateOf(inp),card=inp.closest('.relative');
 return {zona:inp.dataset.zona,parametro:inp.dataset.param,valor:estado==='Resultado'?inp.value.trim():estado,estado,
 justificacion:estado==='Resultado'?'':(card?.querySelector('.pc-justificacion')?.value.trim()||''),
 plan_accion:card?.querySelector('.input-plan-accion')?.value.trim()||inp.dataset.pcPlan||''};
}
window.enviarFormulario=async function(){
 const items=fieldRows().map(itemData);
 if(!items.length){alert('No hay parámetros programados para guardar.');return;}
 for(const item of items){if(item.estado==='Resultado'&&!item.valor){alert('Falta resultado: '+item.zona+' / '+item.parametro);return;}if(item.estado!=='Resultado'&&!item.justificacion){alert('Falta justificación: '+item.zona+' / '+item.parametro);return;}
 }
 if(items.some(i=>i.estado==='Pendiente')&&!confirm('Hay análisis pendientes. ¿Desea guardar el turno?'))return;
 try{
 // La validación definitiva de límites y planes de acción se realiza en el servidor.
 const payload={fecha:$('form_fecha').value,turno:$('form_turno').value,operador:$('form_operador').value,registros:items};
 let res=await fetch(modoEdicion?'/api/plan-calidad/editar':'/api/plan-calidad/guardar',{method:modoEdicion?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 if(!res.ok){
   const error=await res.clone().json().catch(()=>({}));
   const detail=typeof error.detail==='string'?error.detail:'';
   if(detail.startsWith('Plan de acción obligatorio: ')){
     const name=detail.slice('Plan de acción obligatorio: '.length);
     const item=items.find(i=>name===i.zona+' / '+i.parametro);
     if(item){const plan=prompt('Resultado fuera de especificación: '+name+'\nDescriba el plan de acción inicial obligatorio:',item.plan_accion||'');
       if(plan===null)return;
       if(!plan.trim()){alert('El plan de acción no puede quedar vacío.');return;}
       item.plan_accion=plan.trim();
       res=await fetch(modoEdicion?'/api/plan-calidad/editar':'/api/plan-calidad/guardar',{method:modoEdicion?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
     }
   }
 }
 await json(res);alert(modoEdicion?'Registros modificados correctamente.':'Mediciones guardadas correctamente.');modoEdicion=false;cerrarModalFormulario();cargarTablaRegistros();
 }catch(e){alert('No se guardaron los cambios: '+e.message);}
};
async function cargarEdicion(){
 const fecha=$('f_desde').value,turno=$('f_turno').value;
 if(!fecha||!['Turno 1','Turno 2','Turno 3'].includes(turno)){alert('Seleccione una fecha y un turno específico en los filtros.');return;}
 if($('f_hasta').value!==fecha){alert('Para modificar, seleccione la misma fecha en Desde y Hasta.');return;}
 try{
 const data=await json(await fetch(`/api/plan-calidad/registros?f_desde=${fecha}&f_hasta=${fecha}&turno=${encodeURIComponent(turno)}`));
 const rows=data.data||[];if(!rows.length){alert('No hay registros en esa fecha y turno.');return;}
 $('form_fecha').value=fecha;$('form_turno').value=turno;
 $('modalForm').classList.remove('hidden');$('modalForm').classList.add('flex');
 await window.renderizarCamposDinamicos();
 const map=new Map(rows.map(r=>[key(r.zona,r.parametro),r]));
 for(const inp of fieldRows()){
 const r=map.get(key(inp.dataset.zona,inp.dataset.param));if(!r)continue;
 setState(inp,['NA','NC','Pendiente'].includes(r.estado)?r.estado:(['NA','NC','Pendiente'].includes(r.valor)?r.valor:'Resultado'));
 if(stateOf(inp)==='Resultado')inp.value=r.valor||'';
 else {const just=inp.closest('.relative')?.querySelector('.pc-justificacion');if(just)just.value=r.justificacion||'';}
 }
 if(rows[0].operador && [...$('form_operador').options].some(o=>o.value===rows[0].operador))$('form_operador').value=rows[0].operador;
 modoEdicion=true;$('modalForm').querySelector('h3').textContent='✏️ Modificar Mediciones Plan de Calidad';
 $('form_fecha').disabled=true;$('form_turno').disabled=true;
 }catch(e){alert('No se pudo cargar la edición: '+e.message);}
}
const oldCerrar=window.cerrarModalFormulario;
window.cerrarModalFormulario=function(){oldCerrar();$('form_fecha').disabled=false;$('form_turno').disabled=false;modoEdicion=false;};
async function eliminar(){
 const fecha=$('f_desde').value,turno=$('f_turno').value;
 if(!fecha||fecha!==$('f_hasta').value||!['Turno 1','Turno 2','Turno 3'].includes(turno)){alert('Seleccione una sola fecha y un turno específico.');return;}
 try{
 const data=await json(await fetch(`/api/plan-calidad/registros?f_desde=${fecha}&f_hasta=${fecha}&turno=${encodeURIComponent(turno)}`));
 const n=(data.data||[]).length;if(!n){alert('No hay registros para eliminar.');return;}
 if(!confirm(`¿Desea eliminar DEFINITIVAMENTE ${n} registros del ${fecha}, ${turno}?`))return;
 if(!confirm(`CONFIRMACIÓN FINAL: se eliminarán ${n} registros sin posibilidad de recuperarlos. ¿Continuar?`))return;
 await json(await fetch('/api/plan-calidad/eliminar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fecha,turno})}));
 alert('Registros eliminados.');cargarTablaRegistros();
 }catch(e){alert('No fue posible eliminar: '+e.message);}
}
function toolbar(){
 const admin=[...document.querySelectorAll('button')].find(b=>b.getAttribute('onclick')==='abrirModalAdministracion()');
 if(admin){admin.remove();}
 const consultar=[...document.querySelectorAll('button')].find(b=>b.getAttribute('onclick')==='cargarTablaRegistros()');
 if(consultar){
 const editar=document.createElement('button');editar.textContent='✏️ Modificar registro';editar.className='bg-[#2d6a4f] text-white px-3 py-1.5 rounded font-semibold shadow';editar.onclick=cargarEdicion;
 const borrar=document.createElement('button');borrar.textContent='🗑 Eliminar registros';borrar.className='bg-red-700 text-white px-3 py-1.5 rounded font-semibold shadow';borrar.onclick=eliminar;
 consultar.parentElement.append(editar,borrar);
 }
}
// El historial mantiene su tabla original y su desplazamiento.
const oldCargar=window.cargarTablaRegistros;
window.cargarTablaRegistros=async function(){await oldCargar();};
toolbar();
})();
