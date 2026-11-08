/* Adaptador Plan de Calidad: conserva la plantilla original, sin tarjetas V2. */
(function () {
'use strict';
let modoEdicion=false;
const $=id=>document.getElementById(id);
const key=(z,p)=>JSON.stringify([z,p]);
const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function json(res){const data=await res.json().catch(()=>({}));if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));return data;}
function fieldRows(){return [...document.querySelectorAll('#contenedor-parametros .input-medida')];}
function stateOf(inp){return inp.closest('.pc-state-wrap')?.querySelector('.pc-estado')?.value||'Resultado';}
function setState(inp,estado){const wrap=inp.closest('.pc-state-wrap');if(!wrap)return;wrap.querySelector('.pc-estado').value=estado;refreshState(wrap);}
function refreshState(wrap){const estado=wrap.querySelector('.pc-estado').value;const inp=wrap.querySelector('.input-medida');const just=wrap.querySelector('.pc-justificacion');if(estado==='Resultado'){if(['NA','NC','Pendiente'].includes(inp.value))inp.value='';inp.readOnly=false;}else{inp.value=estado;inp.readOnly=true;}inp.disabled=false;inp.placeholder='';just.classList.add('hidden');}
function decorate(){
 for(const inp of fieldRows()){
   if(inp.closest('.pc-state-wrap'))continue;
   const wrap=document.createElement('span');wrap.className='pc-state-wrap flex flex-col gap-1 flex-1 min-w-0';
   inp.parentNode.insertBefore(wrap,inp);wrap.appendChild(inp);
   const sel=document.createElement('select');sel.className='pc-estado border rounded p-1 text-xs bg-gray-50';
   sel.innerHTML='<option value="Resultado" selected hidden></option><option value="NA">NA</option><option value="NC">NC</option><option value="Pendiente">Pendiente</option>';
   const just=document.createElement('input');just.type='text';just.placeholder='';just.className='pc-justificacion hidden border rounded p-1 text-xs w-full';
   wrap.append(sel,just);inp.placeholder='';sel.addEventListener('change',()=>refreshState(wrap));
   // Reutilizar la evaluación original de rango, pero pedir el plan al guardar.
   inp.addEventListener('change',()=>{if(stateOf(inp)==='Resultado'&&inp.value)try{validarCasillaMedicion(inp)}catch(_){}});
 }
}
const oldRender=window.renderizarCamposDinamicos;
window.renderizarCamposDinamicos=async function(){await oldRender();decorate();};
const oldAbrir=window.abrirModalFormulario;
window.abrirModalFormulario=function(){modoEdicion=false;oldAbrir();$('modalForm').querySelector('h3').textContent='📝 Registrar Mediciones Plan de Calidad';};
function itemData(inp){
 const wrap=inp.closest('.pc-state-wrap'),estado=stateOf(inp);
 return {zona:inp.dataset.zona,parametro:inp.dataset.param,valor:estado==='Resultado'?inp.value.trim():estado,estado,
 justificacion:estado==='Resultado'?'':wrap.querySelector('.pc-justificacion').value.trim(),plan_accion:inp.dataset.pcPlan||''};
}
async function ensurePlans(items){
 for(const item of items){if(item.estado!=='Resultado')continue;
 const inp=fieldRows().find(x=>x.dataset.zona===item.zona&&x.dataset.param===item.parametro);
 if(!inp)continue;
 // La validación final se efectúa en el servidor. El formulario emergente permite documentar la desviación.
 const cont=$(inp.dataset.containerId);
 if(cont&&!cont.classList.contains('hidden')){
   const existing=inp.dataset.pcPlan||cont.querySelector('textarea')?.value||'';
   const plan=prompt('Resultado fuera de especificación: '+item.zona+' / '+item.parametro+'\nDescriba el plan de acción inicial obligatorio:',existing);
   if(plan===null)throw new Error('Guardado cancelado: falta revisar el plan de acción.');
   item.plan_accion=plan.trim();inp.dataset.pcPlan=plan.trim();
 }
 }
}
window.enviarFormulario=async function(){
 const items=fieldRows().map(itemData);
 if(!items.length){alert('No hay parámetros programados para guardar.');return;}
 for(const item of items){if(item.estado==='Resultado'&&!item.valor){alert('Falta resultado: '+item.zona+' / '+item.parametro);return;}
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
 oldAbrir();$('form_fecha').value=fecha;$('form_turno').value=turno;
 await window.renderizarCamposDinamicos();
 const map=new Map(rows.map(r=>[key(r.zona,r.parametro),r]));
 for(const inp of fieldRows()){
 const r=map.get(key(inp.dataset.zona,inp.dataset.param));if(!r)continue;
 setState(inp,['NA','NC','Pendiente'].includes(r.estado)?r.estado:(['NA','NC','Pendiente'].includes(r.valor)?r.valor:'Resultado'));
 if(stateOf(inp)==='Resultado')inp.value=r.valor||'';
 else inp.closest('.pc-state-wrap').querySelector('.pc-justificacion').value=r.justificacion||'';
 }
 $('form_operador').value=rows[0].operador||$('form_operador').value;
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
