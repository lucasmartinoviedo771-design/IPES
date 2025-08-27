(function(){
  const onReady=(fn)=>document.readyState!='loading'?fn():document.addEventListener('DOMContentLoaded',fn);
  onReady(()=>{
    const form=document.querySelector('form[data-planes-url]');
    if(!form) return;

    const planesUrl=form.getAttribute('data-planes-url');
    const prefillEst=form.getAttribute('data-prefill-est')||'';
    const CERT_LABEL=(window.CERT_DOCENTE_LABEL||'Certificación Docente para la Educación Secundaria').trim();

    const selEst=document.getElementById('id_estudiante');
    const selProf=document.getElementById('id_profesorado');
    const selPlan=document.getElementById('id_plan');

    const rowTituloSec=document.getElementById('row-titulo-sec');
    const rowTituloTramite=document.getElementById('row-titulo-tramite');
    const rowAdeuda=document.getElementById('row-adeuda');
    const adeudaExtra=document.getElementById('adeuda-extra');

    const f=(id)=>document.getElementById(id);
    const chk={
      dni:f('id_req_dni'),
      certMed:f('id_req_cert_med'),
      fotos:f('id_req_fotos'),
      folios:f('id_req_folios'),
      tituloSec:f('id_req_titulo_sec'),
      tituloTramite:f('id_req_titulo_tramite'),
      adeuda:f('id_req_adeuda'),
      tituloSup:f('id_req_titulo_sup'),
      incumbencias:f('id_req_incumbencias'),
      condicion:f('id_req_condicion'),
      ddjj:f('id_ddjj_compromiso'),
    };

    const pillReg=document.getElementById('pill-regular');
    const pillCond=document.getElementById('pill-cond');
    const ddjjWrap=document.getElementById('ddjj-wrap');

    if(prefillEst && selEst){
      const opt=Array.from(selEst.options).find(o=>o.value==prefillEst);
      if(opt) selEst.value=prefillEst;
    }

    async function loadPlanes(profId){
      if(!selPlan) return;
      selPlan.disabled=true;
      selPlan.innerHTML=`<option value="">Cargando…</option>`;
      try{
        if(!profId){ selPlan.innerHTML=`<option value="">---------</option>`; return; }
        const r=await fetch(`${planesUrl}?prof_id=${encodeURIComponent(profId)}`,{credentials:'same-origin'});
        const data=await r.json();
        const opts=[`<option value="">---------</option>`].concat((data.items||[]).map(it=>`<option value="${it.id}">${it.label}</option>`));
        selPlan.innerHTML=opts.join('');
      }catch(e){
        selPlan.innerHTML=`<option value="">(error)</option>`;
        console.error(e);
      }finally{
        selPlan.disabled=false;
      }
    }

    function isCertDocente(){
      if(!selProf) return false;
      const txt=(selProf.options[selProf.selectedIndex]||{}).text||'';
      return txt.trim()===CERT_LABEL;
    }

    function toggleAdeudaExtras(){
      const on=!!chk.adeuda?.checked;
      adeudaExtra?.classList.toggle('hidden',!on);
      const mats=f('id_req_adeuda_mats');
      const inst=f('id_req_adeuda_inst');
      if(mats) mats.required=on;
      if(inst) inst.required=on;
    }

    function enforceMutual(){
      const group=[chk.tituloSec,chk.tituloTramite,chk.adeuda].filter(Boolean);
      const onCount=group.filter(x=>x.checked).length;
      if(onCount>1){
        const firstOn=group.find(x=>x.checked);
        group.forEach(x=>{ if(x!==firstOn) x.checked=false; });
      }
    }

    function toggleByCarrera(){
      const isCert=isCertDocente();
      // generales SIEMPRE visibles; oculto solo títuloSec / trámite / adeuda cuando es certificación
      [rowTituloSec,rowTituloTramite,rowAdeuda].forEach(el=>el?.classList.toggle('hidden',isCert));
      if(isCert){
        if(chk.tituloSec) chk.tituloSec.checked=false;
        if(chk.tituloTramite) chk.tituloTramite.checked=false;
        if(chk.adeuda) chk.adeuda.checked=false;
        toggleAdeudaExtras();
      }
      // mostrar bloque específico de certificación
      document.getElementById('req-cert-docente')?.classList.toggle('hidden',!isCert);
      computeEstado();
    }

    function computeEstado(){
      const isCert=isCertDocente();
      let ok;

      if(isCert){
        ok = !!(chk.dni?.checked && chk.certMed?.checked && chk.fotos?.checked && chk.folios?.checked && chk.tituloSup?.checked && chk.incumbencias?.checked);
        // no hay flags condicionales por trámite/adeuda aquí
        var condFlags = false;
      }else{
        ok = !!(chk.dni?.checked && chk.certMed?.checked && chk.fotos?.checked && chk.folios?.checked && chk.tituloSec?.checked);
        var condFlags = (!!chk.tituloTramite?.checked) || (!!chk.adeuda?.checked);
      }

      // nuevo requisito: “Condición” debe estar marcado para ser REGULAR
      const condicionOk = !!chk.condicion?.checked;
      const regular = ok && !condFlags && condicionOk;

      pillReg?.classList.toggle('hidden', !regular);
      pillCond?.classList.toggle('hidden', regular);
      ddjjWrap?.classList.toggle('hidden', regular);
      if(regular && chk.ddjj) chk.ddjj.checked=false;
    }

    selProf?.addEventListener('change', (e)=>{ loadPlanes(e.target.value); toggleByCarrera(); });
    [chk.dni,chk.certMed,chk.fotos,chk.folios,chk.tituloSec,chk.tituloTramite,chk.adeuda,chk.tituloSup,chk.incumbencias,chk.condicion]
      .filter(Boolean).forEach(el=>{
        el.addEventListener('change', ()=>{ enforceMutual(); toggleAdeudaExtras(); computeEstado(); });
      });

    toggleByCarrera();
    toggleAdeudaExtras();
    computeEstado();

    if(selProf && selProf.value){ loadPlanes(selProf.value); }
  });
})();