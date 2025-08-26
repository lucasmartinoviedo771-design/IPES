(function () {
  function $(sel) { return document.querySelector(sel); }
  function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

  const chkLegal = $('#titulo_secundario_legalizado');
  const chkTramite = $('#titulo_en_tramite');
  // tolera ambos ids (por si existe el plural en alguna plantilla vieja)
  const chkAdeuda = $('#adeuda_materia') || $('#adeuda_materias');
  const adeudaBlock = $('#adeuda_fields');
  const adeudaInputs = $all('#adeuda_fields input, #adeuda_fields select, #adeuda_fields textarea');

  const hiddenCond = $('#id_condicion');
  const badge = $('#condicion_badge');

  if (!chkAdeuda) {
    console.warn('[inscripcion_profesorado] No encontré #adeuda_materia. Revisar ID en la plantilla.');
    return;
  }

  function toggleAdeuda() {
    const on = chkAdeuda.checked;
    if (!adeudaBlock) return;

    adeudaBlock.classList.toggle('d-none', !on);
    adeudaBlock.classList.toggle('hidden', !on);

    adeudaInputs.forEach(inp => {
      inp.disabled = !on;
      if (!on) inp.value = '';
    });
  }

  function setBadge(cond) {
    hiddenCond.value = cond;

    if (!badge) return;
    badge.textContent = cond;

    const map = {
      'Regular': 'text-bg-success',
      'Condicional': 'text-bg-warning',
      'Libre': 'text-bg-secondary'
    };
    badge.classList.remove('text-bg-success', 'text-bg-warning', 'text-bg-secondary');
    badge.classList.add(map[cond] || 'text-bg-secondary');
    badge.dataset.condicion = cond.toLowerCase();
  }

  function calcular() {
    const legal = chkLegal?.checked || false;
    const tramite = chkTramite?.checked || false;
    const adeuda = chkAdeuda?.checked || false;

    let cond = 'Libre';
    if (legal && !adeuda) cond = 'Regular';
    else if (tramite || adeuda) cond = 'Condicional';

    setBadge(cond);
  }

  // Bind
  [chkLegal, chkTramite, chkAdeuda].forEach(chk => {
    if (chk) chk.addEventListener('change', () => {
      toggleAdeuda();
      calcular();
    });
  });

  // Estado inicial
  toggleAdeuda();
  calcular();
})();