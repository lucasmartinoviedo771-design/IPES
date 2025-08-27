// ui/static/ui/js/correlatividades.js
(function(){
  function $(s, ctx){ return (ctx||document).querySelector(s); }
  const form = $('#correl-form');
  if(!form) return;

  const selProf = $('#id_profesorado');
  const selPlan = $('#id_plan');
  const selEsp  = $('#id_espacio');

  const urlPlanes    = form.dataset.planesUrl;
  const urlMaterias  = form.dataset.materiasUrl;
  const urlCorrs     = form.dataset.conrsUrl || form.dataset.corrsUrl || "/ui/api/correlatividades";

  // ---------------- Helpers ----------------
  async function fetchJSON(url){
    const r = await fetch(url, {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'}});
    if (!r.ok) return null;
    try { return await r.json(); } catch { return null; }
  }
  function guessYear(label){
    const s = (label||"").toLowerCase();

    // 1) localizar palabra clave
    const kw = s.match(/(año|ano|anual|cuatr(?:\.|imestre)?)/);
    const seg = kw ? s.slice(0, kw.index) : s.slice(0, 32);

    // 2) primer número 1..4 en ese segmento
    const nums = seg.match(/[1-4]\s*(?:º|°|er|ro)?/g);
    if (nums && nums.length) return parseInt(nums[0], 10);

    // 3) fallback laxo
    const m = s.match(/(?:^|\s)([1-4])(?:\D|$)/);
    return m ? parseInt(m[1], 10) : null;
  }
  function clearGrids(){
    const r = $('#corr-regular-grid');
    const a = $('#corr-aprobada-grid');
    if(r) r.innerHTML = '';
    if(a) a.innerHTML = '';
  }

  // UI de cada bloque por año
  function yearBlock(title, items, fieldName, containerId){
    const box = document.createElement('div');
    const h = document.createElement('h6');
    h.textContent = title;
    h.className = 'text-sm font-semibold mb-2';
    box.appendChild(h);

    const wrap = document.createElement('div');
    wrap.className = 'space-y-1';

    items.forEach(it=>{
      const row = document.createElement('label');
      row.className = 'flex items-center gap-2 text-sm';
      const id = `${containerId}_${title.replace(/\s+/g,'').toLowerCase()}_${it.id}`;
      row.innerHTML = `
        <input type="checkbox" id="${id}" name="${fieldName}" value="${it.id}"
               class="h-4 w-4 rounded border-slate-300 text-slate-700 focus:ring-2 focus:ring-slate-500">
        <span>${it.label}</span>`;
      wrap.appendChild(row);
    });

    box.appendChild(wrap);
    return box;
  }

  // Render 2 columnas: izq (1º,2º) | der (3º,4º) + "Otros" abajo si existe
  function renderChecks2Cols(container, fieldName, items){
    const groups = {1:[],2:[],3:[],4:[],otros:[]};
    (items||[]).forEach(it=>{
      const yr = (it.year ?? guessYear(it.label));
      const key = (yr>=1 && yr<=4) ? yr : 'otros';
      groups[key].push(it);
    });

    const left = document.createElement('div');
    left.className = 'space-y-4';
    left.appendChild(yearBlock('1º Año', groups[1], fieldName, container.id));
    left.appendChild(yearBlock('2º Año', groups[2], fieldName, container.id));

    const right = document.createElement('div');
    right.className = 'space-y-4';
    right.appendChild(yearBlock('3º Año', groups[3], fieldName, container.id));
    right.appendChild(yearBlock('4º Año', groups[4], fieldName, container.id));

    container.innerHTML = '';
    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-1 lg:grid-cols-2 gap-6';
    grid.appendChild(left);
    grid.appendChild(right);
    container.appendChild(grid);

    if(groups.otros.length){
      const extra = document.createElement('div');
      extra.className = 'mt-4';
      extra.appendChild(yearBlock('Otros', groups.otros, fieldName, container.id));
      container.appendChild(extra);
    }
  }

  function checkByIds(containerSelector, ids){
    const set = new Set((ids||[]).map(String));
    const root = $(containerSelector);
    if(!root) return;
    root.querySelectorAll('input[type=checkbox]').forEach(chk=>{
      chk.checked = set.has(chk.value);
    });
  }

  // ---------- eventos ----------
  async function onProfChange(){
    const profId = selProf.value;
    selPlan.innerHTML = '<option value="">—</option>';
    selEsp.innerHTML  = '<option value="">—</option>';
    clearGrids();
    if(!profId) return;

    const data = await fetchJSON(`${urlPlanes}?prof_id=${encodeURIComponent(profId)}`);
    (data?.items || []).forEach(it=>{
      const opt = document.createElement('option');
      opt.value = it.id; opt.textContent = it.label;
      selPlan.appendChild(opt);
    });
  }

  async function onPlanChange(){
    const planId = selPlan.value;
    selEsp.innerHTML = '<option value="">—</option>';
    clearGrids();
    if(!planId) return;

    const data = await fetchJSON(`${urlMaterias}?plan_id=${encodeURIComponent(planId)}`);
    const items = data?.items || [];

    // combo Materia (ya viene ordenado del API)
    items.forEach(it=>{
      const opt = document.createElement('option');
      opt.value = it.id; opt.textContent = it.label;
      selEsp.appendChild(opt);
    });

    // Grids
    renderChecks2Cols($('#corr-regular-grid'),  'correlativas_regular',  items);
    renderChecks2Cols($('#corr-aprobada-grid'), 'correlativas_aprobada', items);

    // si ya hay una materia seleccionada, precargar
    if(selEsp.value) onEspChange();
  }

  async function onEspChange(){
    const espId = selEsp.value;
    if(!espId) return;
    const data = await fetchJSON(`${urlCorrs}?espacio_id=${encodeURIComponent(espId)}`);
    if(!data) return;
    checkByIds('#corr-regular-grid',  data.regular);
    checkByIds('#corr-aprobada-grid', data.aprobada);
  }

  selProf && selProf.addEventListener('change', onProfChange);
  selPlan && selPlan.addEventListener('change', onPlanChange);
  selEsp  && selEsp .addEventListener('change', onEspChange);
})();