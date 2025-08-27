(function () {
  const form = document.querySelector('form[data-planes-url]');
  if (!form) return;

  const urlPlanes = form.dataset.planesUrl;
  const urlPlanesEl = document.getElementById('id_plan');        // select Plan
  const profSelect = document.getElementById('id_profesorado');   // select Profesorado/Carrera
  const planErrEl  = document.getElementById('plan-error');

  function setOptions(select, items, placeholder) {
    const frag = document.createDocumentFragment();
    const opt0 = document.createElement('option');
    opt0.value = '';
    opt0.textContent = placeholder || '---------';
    frag.appendChild(opt0);
    (items || []).forEach(it => {
      const opt = document.createElement('option');
      opt.value = it.id;
      opt.textContent = it.label;
      frag.appendChild(opt);
    });
    select.innerHTML = '';
    select.appendChild(frag);
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

  async function fetchJSONVerbose(url) {
    try {
      const r = await fetch(url, { credentials: 'same-origin' });
      if (!r.ok) {
        const body = await r.text();
        const msg = `HTTP ${r.status} ${r.statusText} — ${body.slice(0, 300)}`;
        console.error('[planes] fallo fetch:', url, msg);
        showPlanError(msg);
        return { items: [], __error: msg };
      }
      const data = await r.json();
      clearPlanError();
      console.debug('[planes] OK', url, data);
      return data;
    } catch (err) {
      console.error('[planes] error de red:', url, err);
      showPlanError(err.message);
      return { items: [], __error: err.message };
    }
  }

  async function loadPlanesFor(profId) {
    urlPlanesEl.disabled = true;
    setOptions(urlPlanesEl, [], 'Cargando planes...');
    clearPlanError();

    if (!profId) { setOptions(urlPlanesEl, [], '---------'); return; }

    const url = `${urlPlanes}?prof_id=${encodeURIComponent(profId)}`;
    const data = await fetchJSONVerbose(url);

    if (data.__error) {
      setOptions(urlPlanesEl, [], '{error}');
      urlPlanesEl.disabled = true;
      return;
    }

    setOptions(urlPlanesEl, data.items || [], (data.items?.length ? 'Seleccione un plan' : '(sin planes)'));
    urlPlanesEl.disabled = !(data.items && data.items.length);
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
