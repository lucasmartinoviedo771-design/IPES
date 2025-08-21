/*! panel_hooks.js (v2) — mejoras no invasivas para el panel unificado */
(function () {
  function onReady(fn){ if(document.readyState!=='loading'){ fn(); } else { document.addEventListener('DOMContentLoaded', fn); } }
  function norm(s){ return String(s||'').trim().toLowerCase(); }

  onReady(function(){
    try{
      // ===== 1) Adeuda =====
      const adeudaChk  = document.querySelector('input[name="adeuda_materias"]');
      const adeudaWraps = document.querySelectorAll('.js-adeuda-field');
      function toggleAdeuda(){
        if(!adeudaChk) return;
        const on = adeudaChk.checked;
        adeudaWraps.forEach(box=>{
          if(!box) return;
          box.style.display = on ? '' : 'none';
          box.querySelectorAll('input,textarea,select').forEach(el => el.disabled = !on);
        });
      }
      adeudaChk && adeudaChk.addEventListener('change', toggleAdeuda);
      toggleAdeuda();

      // ===== 2) Certificación docente =====
      const profSel = document.querySelector('select[name="profesorado"]');
      const titSec  = document.querySelector('input[name="doc_titulo_sec_legalizado"]');
      const titSup  = document.querySelector('input[name="doc_titulo_superior_legalizado"]');
      const inc     = document.querySelector('input[name="doc_incumbencias_titulo"]');
      function toggleCertDoc(){
        if(!profSel) return;
        const txt = (profSel.options[profSel.selectedIndex]?.text || '').toLowerCase();
        const esCert = txt.includes('certificacion docente') || txt.includes('certificación docente');
        if(titSec){ titSec.closest('label').style.display = esCert ? 'none' : ''; titSec.disabled = esCert; }
        [titSup, inc].forEach(el => { if(!el) return; el.closest('label').style.display = esCert ? '' : 'none'; el.disabled = !el.closest('label').style.display ? false : true; });
      }
      profSel && profSel.addEventListener('change', toggleCertDoc);
      toggleCertDoc();

      // ===== 3) Inscripción -> Espacios =====
      const actionInput = document.querySelector('[name="action"]');
      const actionVal = actionInput ? actionInput.value : '';
      const inscSel   = document.getElementById('id_inscripcion') || document.querySelector('select[name="inscripcion"]');
      const espacioSel= document.getElementById('id_espacio')      || document.querySelector('select[name="espacio"]');

      // Buscar SOLO el campo 'condicion' (nunca el de 'estado')
      const condSel =
        document.getElementById('id_condicion') ||
        document.querySelector('select[name="condicion"]');

      const isRegularidad = (actionVal === 'cargar_cursada');
      const isFinalForm   = (actionVal === 'cargar_nota_final' || actionVal === 'cargar_final_resultado' || actionVal === 'insc_final');
      const shouldWireAjax = isRegularidad || isFinalForm || (actionVal === 'insc_esp');

      function restrictCondOptions(allowed){
        if (!condSel) return;
        const allow = (allowed || []).map(norm);
        let keepSelected = false;
        for (const opt of Array.from(condSel.options)) {
          if (opt.value === '') { opt.hidden = false; opt.disabled = false; continue; }
          const ok = (!allow.length) ||
                     allow.includes(norm(opt.value)) ||
                     allow.includes(norm(opt.text));
          opt.hidden = !ok;
          opt.disabled = !ok;
          if (ok && opt.selected) keepSelected = true;
        }
        if (!keepSelected) condSel.value = '';
      }

      function getAllowedFromSelected(){
        const opt = espacioSel && espacioSel.options[espacioSel.selectedIndex];
        if (!opt) return [];
        try{ if (opt.dataset && opt.dataset.cond){ return opt.dataset.cond.split(',').filter(Boolean); } }catch(_){}
        try{ if (opt.dataset && opt.dataset.conds){ return JSON.parse(opt.dataset.conds || '[]'); } }catch(_){}
        return [];
      }

      async function fillEspacios(inscId){
        if (!espacioSel) return;
        espacioSel.innerHTML = '<option value="">Cargando...</option>';
        espacioSel.disabled = true;
        restrictCondOptions([]);

        if (!inscId){
          espacioSel.innerHTML = '<option value="">---------</option>';
          espacioSel.disabled = false;
          return;
        }

        try{
          const res = await fetch(`/api/espacios-por-inscripcion/${inscId}/`, {credentials:'same-origin'});
          const { ok, items, cond_opts } = await res.json();
          if(!ok) throw new Error('API espacios');
          espacioSel.innerHTML = '<option value="">---------</option>';
          (items || []).forEach(it => {
            const opt = new Option(it.nombre, it.id);
            if (it.cond_opts){ opt.dataset.cond = (it.cond_opts || []).join(','); opt.dataset.conds = JSON.stringify(it.cond_opts || []); }
            espacioSel.add(opt);
          });
          restrictCondOptions(cond_opts || []);
        }catch(e){
          console.error(e);
          espacioSel.innerHTML = '<option value="">Error al cargar</option>';
        }finally{
          espacioSel.disabled = false;
        }
      }

      if (shouldWireAjax && inscSel && espacioSel){
        if (inscSel.value) fillEspacios(inscSel.value);
        inscSel.addEventListener('change', function(){ fillEspacios(this.value); });
        espacioSel.addEventListener('change', function(){ restrictCondOptions(getAllowedFromSelected()); });
      }

      // ===== 4) Condición según espacio =====
      async function syncCondicionFromAPI(){
        const espId = espacioSel && espacioSel.value;
        if(!espId || !condSel) return;
        try{
          const r = await fetch(`/api/condiciones-por-espacio/${espId}/`, {credentials:'same-origin'});
          const data = await r.json();
          const choices = (data && data.ok && data.choices) ? data.choices : [];
          if (choices.length){
            condSel.innerHTML = choices.map(([v,l]) => `<option value="${v}">${l}</option>`).join('');
          }
        }catch(err){ console.warn('condicion api', err); }
      }
      espacioSel && espacioSel.addEventListener('change', function(){
        const allowed = getAllowedFromSelected();
        if (allowed.length){ restrictCondOptions(allowed); }
        else { syncCondicionFromAPI(); }
      });
      if (espacioSel && condSel && !getAllowedFromSelected().length){ syncCondicionFromAPI(); }

      // ===== 5) Correlatividades =====
      async function cargarCorrelatividades(){
        const inscSel2 = inscSel;
        const espSel2  = espacioSel;
        const list     = document.getElementById('correl-list');
        const sum      = document.getElementById('correl-summary');
        if(!inscSel2 || !espSel2 || !list) return;

        list.innerHTML = '';
        sum && (sum.textContent = '');

        const inscId = inscSel2.value;
        const espId  = espSel2.value;
        if(!espId) return;

        const url = new URL(window.location.origin + `/api/correlatividades/${espId}/`);
        if(inscId) url.searchParams.set('insc_id', inscId);

        try{
          const res = await fetch(url.toString(), {credentials:'same-origin'});
          const data = await res.json();
          if(!data.ok) throw new Error('API correlatividades');
          const detalles = data.detalles || [];
          if(!detalles.length){
            list.innerHTML = '<li class="muted">(Sin correlatividades definidas)</li>';
          } else {
            detalles.forEach(d => {
              const li = document.createElement('li');
              const estado = d.estado_encontrado || '—';
              li.textContent = `${d.cumplido ? '✅' : '⛔'} ${d.etiqueta} · mínimo: ${d.minimo} · actual: ${estado}`;
              list.appendChild(li);
            });
          }
          if(sum && typeof data.puede_cursar === 'boolean'){ sum.textContent = data.puede_cursar ? 'Puede cursar.' : 'No cumple correlatividades.'; }
        }catch(e){
          console.warn(e);
          list.innerHTML = '<li class="muted">(No se pudieron cargar correlatividades)</li>';
        }
      }
      if (document.getElementById('correl-list')){
        espacioSel && espacioSel.addEventListener('change', cargarCorrelatividades);
        inscSel && inscSel.addEventListener('change', ()=>setTimeout(cargarCorrelatividades, 100));
        cargarCorrelatividades();
      }

      // ===== 6) Finales =====
      const nota = document.querySelector('[name="nota_final"], [name="nota_num"], [name="nota"]');
      const ausente = document.querySelector('[name="ausente"]');
      const justif  = document.querySelector('[name="ausencia_justificada"]');
      const condicion = document.querySelector('[name="condicion"], #id_condicion');
      const notaTexto = document.querySelector('[name="nota_texto"]');
      const dispoInt  = document.querySelector('[name="disposicion_interna"]');

      function syncFinales(){
        const isAus = !!(ausente && ausente.checked);
        const cond  = condicion ? condicion.value : null;
        const isEq  = norm(cond) === 'equivalencia';

        function show(el, on){ if(!el) return; const wrap = el.closest('.item, .row, label, div') || el; wrap.style.display = on ? '' : 'none'; }
        function dis(el, on){ if(!el) return; el.disabled = !!on; }

        if (condicion) {
          show(notaTexto, isEq); show(dispoInt, isEq);
          show(ausente, !isEq); show(justif, !isEq && isAus);
          show(nota,    !isEq && !isAus); dis(nota, isEq || isAus);
        } else {
          dis(nota, isAus); show(nota, !isAus); show(justif, isAus);
        }

        if (nota && !nota._hasRangeListener) {
          nota.setAttribute('min','0'); nota.setAttribute('max','10');
          nota.addEventListener('input',function(){
            if(this.value===''){this.setCustomValidity('');return;}
            let v=parseFloat(String(this.value).replace(',','.'));
            if(isNaN(v)||v<0||v>10){this.setCustomValidity('La nota debe estar entre 0 y 10.');}
            else{this.setCustomValidity('');}
          });
          nota._hasRangeListener = true;
        }
      }
      if (isFinalForm){
        ausente && ausente.addEventListener('change', syncFinales);
        justif  && justif.addEventListener('change', syncFinales);
        condicion && condicion.addEventListener('change', syncFinales);
        syncFinales();
      }

    }catch(e){ console.warn('panel_hooks v2 error:', e); }
  });
})();
