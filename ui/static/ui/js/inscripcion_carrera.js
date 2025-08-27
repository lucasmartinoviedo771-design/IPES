(function () {
  const form = document.querySelector('form[data-planes-url]');
  if (!form) return;

  const urlPlanes = form.dataset.planesUrl;
  const planSelect = document.getElementById('id_plan');
  const profSelect = document.getElementById('id_profesorado');
  const planErrEl  = document.getElementById('plan-error');

  function resetPlanSelect(sel) {
    sel.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— Seleccioná un plan —";
    sel.appendChild(opt);
    sel.value = "";
  }

  function populatePlanes(sel, items) {
    resetPlanSelect(sel);
    for (const it of items) {
      const opt = document.createElement("option");
      opt.value = it.id;
      opt.textContent = it.label;
      sel.appendChild(opt);
    }
    if (items.length === 1) {
      sel.value = String(items[0].id);
      sel.dispatchEvent(new Event("change"));
    }
  }

  function showPlanError(msg) {
    if (!planErrEl) return;
    planErrEl.textContent = msg;
    planErrEl.classList.remove('hidden');
  }

  function clearPlanError() {
    if (!planErrEl) return;
    planErrEl.textContent = '';
    planErrEl.classList.add('hidden');
  }

  async function fetchPlanes(url) {
    try {
      const r = await fetch(url, {credentials: "same-origin"});
      if (!r.ok) {
        const body = await r.text();
        const msg = `HTTP ${r.status} ${r.statusText} — ${body.slice(0, 300)}`;
        throw new Error(msg);
      }
      const data = await r.json();
      return data.items || [];
    } catch (err) {
      console.error("Error cargando planes:", err);
      showPlanError(err.message);
      alert("No pudimos cargar los planes. Probá recargar la página.");
      return [];
    }
  }

  async function loadPlanesFor(profId) {
    planSelect.disabled = true;
    resetPlanSelect(planSelect);
    clearPlanError();

    if (!profId) {
        planSelect.disabled = true;
        return;
    }

    const url = `${urlPlanes}?prof_id=${encodeURIComponent(profId)}`;
    const items = await fetchPlanes(url);

    populatePlanes(planSelect, items);
    planSelect.disabled = items.length === 0;
  }

  // Cargar al inicio si ya hay profesor preseleccionado
  if (profSelect && profSelect.value) {
    loadPlanesFor(profSelect.value);
  }

  // Cambios de carrera -> recargar planes
  if (profSelect) {
    profSelect.addEventListener('change', () => loadPlanesFor(profSelect.value));
  }
})();