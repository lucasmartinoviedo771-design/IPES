// ui/static/ui/js/inscripcion_profesorado.js
(function () {
  // util: agrega o quita hidden / d-none (funciona con ambos estilos)
  function setHidden(el, hide) {
    if (!el) return;
    if (hide) {
      el.classList.add('hidden');    // Tailwind
      el.classList.add('d-none');    // Bootstrap
    } else {
      el.classList.remove('hidden');
      el.classList.remove('d-none');
    }
  }

  // Mostrar/ocultar bloque "Adeuda materia"
  function wireAdeuda() {
    var chk = document.getElementById('adeuda_materia');
    var box = document.getElementById('adeuda_fields');
    if (!chk || !box) return;
    var inputs = box.querySelectorAll('input,select,textarea');

    function sync() {
      var on = !!chk.checked;
      setHidden(box, !on);
      inputs.forEach(function (i) {
        i.disabled = !on;
        if (!on) i.value = '';
      });
    }
    chk.addEventListener('change', sync);
    sync(); // primera carga
  }

  // Cálculo de condición (ajustá reglas si querés)
  // - Regular: título legalizado y NO adeuda
  // - Condicional: título en trámite O adeuda
  // - Libre: todo lo demás
  function wireCondicion() {
    var idCond = document.getElementById('id_condicion');          // hidden o input
    var badge  = document.getElementById('condicion_badge');       // badge visual (opcional)

    // checkboxes
    var chkLegal   = document.getElementById('titulo_secundario_legalizado');
    var chkTramite = document.getElementById('titulo_en_tramite');
    var chkAdeuda  = document.getElementById('adeuda_materia');

    if (!idCond && !badge) return; // si no hay a dónde escribir, no cablear

    function calcular() {
      var legal   = !!(chkLegal && chkLegal.checked);
      var tramite = !!(chkTramite && chkTramite.checked);
      var adeuda  = !!(chkAdeuda && chkAdeuda.checked);

      var r = 'Libre';
      if (legal && !adeuda) {
        r = 'Regular';
      } else if (tramite || adeuda) {
        r = 'Condicional';
      }

      if (idCond) idCond.value = r;
      if (badge) {
        badge.textContent = r;
        badge.dataset.condicion = r.toLowerCase(); // por si querés estilizar por data-attr
      }
    }

    ['change', 'input'].forEach(function (ev) {
      [chkLegal, chkTramite, chkAdeuda].forEach(function (el) {
        if (el) el.addEventListener(ev, calcular);
      });
    });

    calcular(); // primera carga
  }

  document.addEventListener('DOMContentLoaded', function () {
    wireAdeuda();
    wireCondicion();
  });
})();