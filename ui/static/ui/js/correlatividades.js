// ui/static/ui/js/correlatividades.js
(function(){
  function $(s, ctx){ return (ctx||document).querySelector(s); }
  const form = $('#correl-form');
  if(!form) return;

  const selProf = $('#id_profesorado');
  const selPlan = $('#id_plan');
  const selEsp  = $('#id_espacio');

  const urlPlanes   = form.dataset.planesUrl;    // /ui/api/planes?prof_id=
  const urlMaterias = form.dataset.materiasUrl;  // /ui/api/materias-por-plan?plan_id=

  async function fetchJSON(url){
    const r = await fetch(url, {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'}});
    if (!r.ok) return {items:[]};
    try { return await r.json(); } catch { return {items:[]}; }
  }

  async function onProfChange(){
    const profId = selProf.value;
    selPlan.innerHTML = '<option value="">—</option>';
    selEsp.innerHTML = '<option value="">—</option>';
    if(!profId) return;
    const data = await fetchJSON(`${urlPlanes}?prof_id=${encodeURIComponent(profId)}`);
    (data.items||[]).forEach(it=>{
      const opt = document.createElement('option');
      opt.value = it.id; opt.textContent = it.label;
      selPlan.appendChild(opt);
    });
  }

  async function onPlanChange(){
    const planId = selPlan.value;
    selEsp.innerHTML = '<option value="">—</option>';
    if(!planId) return;

    const data = await fetchJSON(`${urlMaterias}?plan_id=${encodeURIComponent(planId)}`);

    // Poblar select de materia
    (data.items||[]).forEach(it=>{
      const opt = document.createElement('option');
      opt.value = it.id; opt.textContent = it.label;
      selEsp.appendChild(opt);
    });

    // Poblar checkboxes de ambos grupos (limpiando los existentes)
    function fillChecks(containerId, fieldName){
      const container = document.getElementById(containerId);
      if(!container) return;

      // Limpia UL/LI generados por CheckboxSelectMultiple
      container.querySelectorAll('li').forEach(li=>li.remove());
      const ul = container.querySelector('ul') || container;

      (data.items||[]).forEach(it=>{
        const li = document.createElement('li');
        li.className = 'form-check';
        const id = `${containerId}_${it.id}`;
        li.innerHTML = `
          <input class="form-check-input" type="checkbox" id="${id}" name="${fieldName}" value="${it.id}">
          <label class="form-check-label" for="${id}">${it.label}</label>`;
        ul.appendChild(li);
      });
    }
    fillChecks('id_correlativas_regular', 'correlativas_regular');
    fillChecks('id_correlatividades_aprobada', 'correlativas_aprobada');
  }

  selProf && selProf.addEventListener('change', onProfChange);
  selPlan && selPlan.addEventListener('change', onPlanChange);
})();