/*! panel_hooks.js — actualización: condicion sin fallback a estado + carga de espacios por data-espacios-url */
(function () {
  function onReady(fn){ if(document.readyState!=='loading'){ fn(); } else { document.addEventListener('DOMContentLoaded', fn); } }
  const norm = s => String(s||'').trim().toLowerCase();

  onReady(function(){
    try {
      // ===== 0) Utilidades ligeras =====
      function show(el, on){ if(!el) return; const wrap = el.closest('.item, .row, label, div') || el; wrap.style.display = on ? '' : 'none'; }
      function dis(el, on){ if(!el) return; el.disabled = !!on; }

      // ===== 1) (Opcional) bloques que ya tengas: Adeuda / Certificación Docente =====
      // Si usabas lógica adicional, podés mantenerla aquí arriba.

      // ===== 2) Finales (mostrar/ocultar según ausente/equivalencia) =====
      (function finalesBlock(){
        const nota      = document.querySelector('[name="nota_final"], [name="nota_num"], [name="nota"]');
        const ausente   = document.querySelector('[name="ausente"]');
        const justif    = document.querySelector('[name="ausencia_justificada"]');
        const condicion = document.querySelector('[name="condicion"], #id_condicion');
        const notaTexto = document.querySelector('[name="nota_texto"]');
        const dispoInt  = document.querySelector('[name="disposicion_interna"]');

        function syncFinales(){
          const isAus = !!(ausente && ausente.checked);
          const cond  = condicion ? condicion.value : null;
          const isEq  = norm(cond) === 'equivalencia';

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

        // En formularios de finales normalmente existen estos campos; si no, no pasa nada.
        ausente && ausente.addEventListener('change', syncFinales);
        justif  && justif.addEventListener('change', syncFinales);
        condicion && condicion.addEventListener('change', syncFinales);
        syncFinales();
      })();

      // ===== 3) Inscripción -> Espacios =====

      // ⚠️ Mantenemos la lógica de 'condicion' sin tocar 'estado'
      const condSel =
        document.getElementById('id_condicion') ||
        document.querySelector('select[name="condicion"]');

      if (condSel) {
        // ——— Si tenías funciones para 'condSel', ponelas acá dentro ———
        // Ej: restricciones según el espacio seleccionado o carga por API de choices
        // function restrictCondOptions(allowed) { ... }
        // condSel.addEventListener('change', () => restrictCondOptions([...]));
      }

      // --- SIEMPRE habilitar la carga de ESPACIOS según la INSCRIPCIÓN ---
      const inscSel    = document.getElementById('id_inscripcion') || document.querySelector('select[name="inscripcion"]');
      const espacioSel = document.getElementById('id_espacio')      || document.querySelector('select[name="espacio"]');

      async function loadEspacios(inscId) {
		console.log("-> Se llamó a loadEspacios con el ID:", inscId);
        // Limpia y deja solo la opción vacía
        if (!espacioSel) return;
        espacioSel.innerHTML = '<option value="">---------</option>';

        if (!inscId) return;

        // URL desde data-attribute para no hardcodear rutas
        const baseUrl = inscSel?.dataset?.espaciosUrl;
        if (!baseUrl) return;

        try {
          const url = baseUrl.replace('0', inscId);
          const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
          if (!res.ok) return;
          const data = await res.json(); // Espera: [{id, label}, ...]

          for (const item of data.items) {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.nombre;
            espacioSel.appendChild(opt);
          }
        } catch (e) {
          // opcional: loguear
          console.error('No se pudieron cargar espacios:', e);
        }
      }

      // Cargar al entrar si ya hay inscripción seleccionada y escuchar cambios
      if (inscSel && espacioSel) {
        if (inscSel.value) loadEspacios(inscSel.value);
        inscSel.addEventListener('change', (e) => loadEspacios(e.target.value));
      }

      // ===== 4) Correlatividades (visual) opcional =====
      // Si tu template incluye <ul id="correl-list"> podés mantener esto.
      (function correlatividadesBlock(){
        const list = document.getElementById('correl-list');
        if (!list || !espacioSel) return;

        async function cargarCorrelatividades(){
          const inscId = inscSel ? inscSel.value : '';
          const espId  = espacioSel.value;
          list.innerHTML = '';
          if(!espId){
            list.innerHTML = '<li class="muted">(Sin correlatividades definidas)</li>';
            return;
          }

          try{
            const url = new URL(window.location.origin + `/api/correlatividades/${espId}/`);
            if (inscId) url.searchParams.set('insc_id', inscId);
            const res = await fetch(url.toString(), {credentials:'same-origin'});
            const data = await res.json();

            const detalles = (data && data.ok) ? (data.detalles || []) : [];
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
          }catch(e){
            console.warn('correlatividades:', e);
            list.innerHTML = '<li class="muted">(No se pudieron cargar correlatividades)</li>';
          }
        }

        espacioSel.addEventListener('change', cargarCorrelatividades);
        inscSel && inscSel.addEventListener('change', ()=>setTimeout(cargarCorrelatividades, 100));
        cargarCorrelatividades();
      })();

    } catch (e) {
      console.warn('panel_hooks error:', e);
    }
  });
})();
