(function () {
  const form = document.getElementById("form-insc-mat");
  if (!form) return;

  const urlPlanes   = form.dataset.planesUrl;
  const urlMaterias = form.dataset.materiasUrl;

  const selProf = document.getElementById("id_profesorado");
  const selPlan = document.getElementById("id_plan");
  const selMat  = document.getElementById("id_materia");

  const prefill = (window.__INSCR_MAT_PREFILL__) || {prof:"", plan:"", mat:""};

  function resetSelect(sel, placeholder) {
    sel.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    sel.appendChild(opt);
    sel.value = "";
  }

  function populateSelect(sel, items, placeholder) {
    resetSelect(sel, placeholder);
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

  async function fetchJSON(url, resourceName) {
    try {
      const r = await fetch(url, {credentials: "same-origin"});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      return data.items || [];
    } catch (err) {
      console.error(`Error cargando ${resourceName}:`, err);
      alert(`No pudimos cargar los ${resourceName}. Probá recargar la página.`);
      return [];
    }
  }

  async function loadPlanes(profId, trySelectPrefill=true) {
    selPlan.disabled = true;
    selMat.disabled = true;
    resetSelect(selPlan, "Cargando planes...");
    resetSelect(selMat, "Esperando plan...");

    if (!profId) {
      resetSelect(selPlan, "Esperando carrera...");
      return;
    }

    const url = `${urlPlanes}?prof_id=${encodeURIComponent(profId)}`;
    const items = await fetchJSON(url, "planes");
    
    populateSelect(selPlan, items, "Seleccioná un plan...");
    selPlan.disabled = items.length === 0;

    if (trySelectPrefill && prefill.plan) {
      const exists = Array.from(selPlan.options).some(o => String(o.value) === String(prefill.plan));
      if (exists) {
        selPlan.value = prefill.plan;
        await loadMaterias(prefill.plan, true);
      }
    }
  }

  async function loadMaterias(planId, trySelectPrefill=false) {
    selMat.disabled = true;
    resetSelect(selMat, "Cargando materias...");
    if (!planId) {
      resetSelect(selMat, "Esperando plan...");
      return;
    }

    const url = `${urlMaterias}?plan_id=${encodeURIComponent(planId)}`;
    const items = await fetchJSON(url, "materias");

    populateSelect(selMat, items, "Seleccioná una materia...");
    selMat.disabled = items.length === 0;

    if (trySelectPrefill && prefill.mat) {
      const exists = Array.from(selMat.options).some(o => String(o.value) === String(prefill.mat));
      if (exists) selMat.value = prefill.mat;
    }
  }

  // Listeners
  selProf.addEventListener("change", () => {
    const profId = selProf.value || "";
    prefill.plan = ""; prefill.mat = "";
    loadPlanes(profId, false);
  });

  selPlan.addEventListener("change", () => {
    const planId = selPlan.value || "";
    prefill.mat = "";
    loadMaterias(planId, false);
  });

  // Init (con prefill)
  (async function init() {
    if (selProf.value) {
      await loadPlanes(selProf.value, true);
    } else if (prefill.prof) {
      selProf.value = prefill.prof;
      await loadPlanes(prefill.prof, true);
    }
  })();
})();