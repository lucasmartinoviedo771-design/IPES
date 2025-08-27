(function () {
  const form = document.getElementById("form-insc-mat");
  if (!form) return;

  const urlPlanes   = form.dataset.planesUrl;
  const urlMaterias = form.dataset.materiasUrl;

  const selProf = document.getElementById("id_profesorado");
  const selPlan = document.getElementById("id_plan");
  const selMat  = document.getElementById("id_materia");

  const prefill = (window.__INSCR_MAT_PREFILL__) || {prof:"", plan:"", mat:""};

  function setDisabled(select, disabled) {
    select.disabled = !!disabled;
  }
  function setOptions(select, items, placeholder) {
    const frag = document.createDocumentFragment();
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = placeholder || "---------";
    frag.appendChild(opt0);

    (items || []).forEach(it => {
      const opt = document.createElement("option");
      opt.value = it.id;
      opt.textContent = it.label;
      frag.appendChild(opt);
    });

    select.innerHTML = "";
    select.appendChild(frag);
  }

  async function fetchJSON(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }

  async function loadPlanes(profId, trySelectPrefill=true) {
    setDisabled(selPlan, true);
    setDisabled(selMat, true);
    setOptions(selPlan, [], "Cargando planes...");
    setOptions(selMat, [], "---------");

    if (!profId) {
      setOptions(selPlan, [], "---------");
      return;
    }

    try {
      const data = await fetchJSON(`${urlPlanes}?prof_id=${encodeURIComponent(profId)}`);
      setOptions(selPlan, data.items || [], data.items?.length ? "Seleccione un plan" : "(sin planes)");
      setDisabled(selPlan, false);

      if (trySelectPrefill && prefill.plan) {
        const exists = Array.from(selPlan.options).some(o => String(o.value) === String(prefill.plan));
        if (exists) {
          selPlan.value = prefill.plan;
          await loadMaterias(prefill.plan, true);
        }
      }
    } catch (e) {
      setOptions(selPlan, [], "(error)");
      console.error("Error cargando planes:", e);
    }
  }

  async function loadMaterias(planId, trySelectPrefill=false) {
    setDisabled(selMat, true);
    setOptions(selMat, [], "Cargando materias...");
    if (!planId) { setOptions(selMat, [], "---------"); return; }

    try {
      const data = await fetchJSON(`${urlMaterias}?plan_id=${encodeURIComponent(planId)}`);
      setOptions(selMat, data.items || [], data.items?.length ? "Seleccione una materia" : "(sin materias)");
      setDisabled(selMat, false);

      if (trySelectPrefill && prefill.mat) {
        const exists = Array.from(selMat.options).some(o => String(o.value) === String(prefill.mat));
        if (exists) selMat.value = prefill.mat;
      }
    } catch (e) {
      setOptions(selMat, [], "(error)");
      console.error("Error cargando materias:", e);
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
