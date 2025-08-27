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
  const urlCorrs     = form.dataset.corrsUrl || "/ui/api/correlatividades";

  // ---------- helpers ----------
  async function fetchJSON(url){
    const r = await fetch(url, {credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest'}});
    if (!r.ok) return null;
    try { return await r.json(); } catch { return null; }
  }

  function clearGrids(){
    const r = $('#corr-regular-grid');
    const a = $('#corr-aprobada-grid');
    if(r) r.innerHTML = '';
    if(a) a.innerHTML = '';
  }

  // Grid 5 columnas + clamp de 2 líneas + altura uniforme (sin CSS externo)
function renderChecks3Cols(container, fieldName, items) {
  const COLS = 5;
  const gapX = '2.5rem';
  const gapY = '1rem';
  const lineHeight = 1.25;              // em
  const lines = 2;                       // cantidad de líneas visibles
  const cellHeightEm = (lineHeight * lines).toFixed(2) + 'em';

  // grid contenedor
  const grid = document.createElement('div');
  grid.style.display = 'grid';
  grid.style.gridTemplateColumns = `repeat(${COLS}, minmax(0, 1fr))`;
  grid.style.columnGap = gapX;
  grid.style.rowGap = gapY;
  grid.style.maxWidth = '1280px';
  grid.style.margin = '0 auto';

  (items || []).forEach((it) => {
    const label = document.createElement('label');
    label.style.display = 'flex';
    label.style.alignItems = 'flex-start';
    label.style.gap = '.8rem';
    label.style.fontSize = '15px';
    label.style.lineHeight = String(lineHeight);
    label.style.wordBreak = 'break-word';
    label.style.minHeight = cellHeightEm;  // todas las celdas misma altura

    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.name = fieldName;
    chk.value = it.id;
    chk.style.width = '1.35rem';
    chk.style.height = '1.35rem';
    chk.style.border = '1px solid #cbd5e1';
    chk.style.borderRadius = '.35rem';
    chk.style.flexShrink = '0';

    const span = document.createElement('span');
    span.title = it.label;                 // tooltip con el texto completo
    // clamp a 2 líneas + ellipsis
    span.style.display = '-webkit-box';
    span.style.webkitBoxOrient = 'vertical';
    span.style.webkitLineClamp = String(lines);
    span.style.overflow = 'hidden';
    span.style.textOverflow = 'ellipsis';
    span.style.maxHeight = cellHeightEm;   // fija la altura de texto a 2 líneas

    span.textContent = it.label;

    label.appendChild(chk);
    label.appendChild(span);
    grid.appendChild(label);
  });

  container.innerHTML = '';
  container.appendChild(grid);
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

    // combo Materia (queda en el orden que mande el API; si querés solo alfabético, ordenalo allí)
    items.forEach(it=>{
      const opt = document.createElement('option');
      opt.value = it.id; opt.textContent = it.label;
      selEsp.appendChild(opt);
    });

    // grid de checks en 3 columnas para ambos bloques
    renderChecks3Cols($('#corr-regular-grid'),  'correlativas_regular',  items);
    renderChecks3Cols($('#corr-aprobada-grid'), 'correlativas_aprobada', items);

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