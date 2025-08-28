(function () {
  const form = document.getElementById("form-insc-mat");
  const API_PLANES = form.dataset.apiPlanes;
  const API_MATS = form.dataset.apiMats;
  const API_CORR = form.dataset.apiCorr;

  const selProf = document.getElementById("sel-prof");
  const selPlan = document.getElementById("sel-plan");
  const selAnio = document.getElementById("sel-anio");
  const selCuat = document.getElementById("sel-cuat");
  const tb = document.getElementById("tb-mats");
  const matsCount = document.getElementById("mats-count");

  const prefillProf = document.getElementById("prefill_prof_id").value;
  const prefillPlan = document.getElementById("prefill_plan_id").value;

  // Helpers
  const el = (tag, cls, txt) => {
    const x = document.createElement(tag);
    if (cls) x.className = cls;
    if (txt != null) x.textContent = txt;
    return x;
  };

  function resetSelect(sel, placeholder) {
    sel.innerHTML = "";
    const opt = el("option", "", placeholder || "— Seleccioná —");
    opt.value = "";
    sel.appendChild(opt);
  }

  function setCount(n) {
    matsCount.textContent = n ? `${n} materias` : "";
  }

  async function fetchJSON(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }

  // Render correlatividades en chips
  function renderCorrCell(cell, corr) {
    cell.innerHTML = "";
    const wrap = el("div", "flex flex-wrap gap-1");
    if (corr && corr.regular && corr.regular.length) {
      corr.regular.forEach(name => {
        const chip = el("span", "px-2 py-0.5 text-xs rounded bg-sky-100 text-sky-800", `REG: ${name}`);
        wrap.appendChild(chip);
      });
    }
    if (corr && corr.aprobada && corr.aprobada.length) {
      corr.aprobada.forEach(name => {
        const chip = el("span", "px-2 py-0.5 text-xs rounded bg-emerald-100 text-emerald-800", `APR: ${name}`);
        wrap.appendChild(chip);
      });
    }
    if (!wrap.childNodes.length) {
      wrap.appendChild(el("span", "text-slate-400", "—"));
    }
    cell.appendChild(wrap);
  }

  function passesFilters(row, anio, cuat) {
    if (anio && String(row.plan_anio) !== String(anio)) return false;
    if (cuat && String(row.cuatrimestre) !== String(cuat)) return false;
    return true;
  }

  function renderRows(rows, corrMap) {
    tb.innerHTML = "";
    let count = 0;
    const anio = selAnio.value;
    const cuat = selCuat.value;

    rows.forEach(r => {
      if (!passesFilters(r, anio, cuat)) return;

      const tr = el("tr", "align-top");
      tr.appendChild(el("td", "py-2 pr-3", r.plan_anio ?? "—"));
      tr.appendChild(el("td", "py-2 pr-3", r.cuatrimestre ?? "—"));
      tr.appendChild(el("td", "py-2 pr-3", r.nombre));

      const tdCorr = el("td", "py-2 pr-3");
      const corr = corrMap.get(String(r.id)) || { regular: [], aprobada: [] };
      renderCorrCell(tdCorr, corr);
      tr.appendChild(tdCorr);

      // Estado (placeholder en Fase 1)
      const tdEst = el("td", "py-2 pr-3");
      tdEst.appendChild(el("span", "px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs", "Pendiente"));
      tr.appendChild(tdEst);

      // Checkbox inscripción (en Fase 2 se deshabilita si no cumple)
      const tdChk = el("td", "py-2");
      const chk = el("input");
      chk.type = "checkbox";
      chk.dataset.espacioId = r.id;
      tdChk.appendChild(chk);
      tr.appendChild(tdChk);

      tb.appendChild(tr);
      count += 1;
    });

    setCount(count);
  }

  async function loadCorrelatividades(spaces) {
    // Llamadas paralelas a /ui/api/correlatividades?espacio_id=...
    const map = new Map();
    await Promise.all(spaces.map(async s => {
      try {
        const data = await fetchJSON(`${API_CORR}?espacio_id=${s.id}`);
        // data => { regular: [names], aprobada: [names] }
        map.set(String(s.id), data);
      } catch (e) {
        console.warn("corr fail", s.id, e);
        map.set(String(s.id), { regular: [], aprobada: [] });
      }
    }));
    return map;
  }

  async function loadMateriasByPlan(planId) {
    if (!planId) {
      tb.innerHTML = "";
      setCount(0);
      return;
    }
    try {
      const res = await fetchJSON(`${API_MATS}?plan_id=${planId}`);
      const rows = res.items || [];
      const corrMap = await loadCorrelatividades(rows);
      renderRows(rows, corrMap);
    } catch (e) {
      console.error(e);
      alert("No se pudieron cargar las materias del plan.");
    }
  }

  // Listeners
  selPlan.addEventListener("change", () => loadMateriasByPlan(selPlan.value));
  selAnio.addEventListener("change", () => {
    // Refiltrar sin volver a pedir
    const rows = Array.from(tb.querySelectorAll("tr")).map(tr => tr.__row).filter(Boolean);
  });
  selCuat.addEventListener("change", selAnio.onchange);

  // Bootstrap: si venimos preseleccionados, cargamos straight
  (async function init() {
    // Si ya estás pasando el profesorado precargado desde la página anterior, podés dejar el select vacío y saltar a planes:
    resetSelect(selProf, "— (opcional) —");

    // Cargar planes si viene prefill_prof_id
    if (prefillProf) {
      resetSelect(selPlan, "Cargando planes…");
      try {
        const data = await fetchJSON(`${API_PLANES}?prof_id=${prefillProf}`);
        resetSelect(selPlan, "— Seleccioná un plan —");
        (data.items || []).forEach(p => {
          const o = el("option", "", p.label);
          o.value = p.id;
          selPlan.appendChild(o);
        });
        if (prefillPlan) {
          selPlan.value = String(prefillPlan);
          selPlan.dispatchEvent(new Event("change"));
        }
      } catch (e) {
        console.error(e);
        resetSelect(selPlan, "— Seleccioná un plan —");
      }
    }
  })();

  // Botón de simulación
  document.getElementById("btn-preinscribir").addEventListener("click", () => {
    const a = [];
    tb.querySelectorAll("input[type=checkbox]:checked").forEach(ch => {
      a.push(ch.dataset.espacioId);
    });
    if (!a.length) return alert("No seleccionaste materias.");
    // En Fase 2 hacemos POST real
    alert(`(Simulación) Materias seleccionadas: ${a.join(", ")}`);
  });

})();
