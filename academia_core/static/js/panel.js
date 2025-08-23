// academia_core/static/js/panel.js

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// Alternativa: leer el token del input hidden del form (por si la cookie no está)
function getCsrfFromForm() {
  const el = document.querySelector('#form-inscribir input[name=csrfmiddlewaretoken]');
  return el ? el.value : null;
}

/* ----------------------------- DEFENSA ESTADO ----------------------------- */
// Defensa: asegurar que el <select name="estado"> tenga opciones
function ensureEstadoOptions(force) {
  const form = document.querySelector('#form-inscribir') || document;
  const sel = form.querySelector('[name="estado"]') || document.getElementById('id_estado');
  if (!sel) return;
  const needsFill = !sel.options || sel.options.length === 0;
  if (needsFill) {
    sel.innerHTML = '';
    sel.appendChild(new Option('En curso', 'EN_CURSO'));
    sel.appendChild(new Option('Baja', 'BAJA'));
    if (force) sel.value = 'EN_CURSO';
  }
}

// Asegurar opciones apenas carga el DOM
document.addEventListener('DOMContentLoaded', function () {
  ensureEstadoOptions(true);
});

// Cuando cambian campos que disparan re-render de secciones (via AJAX/DOM updates)
document.addEventListener('change', function (e) {
  const watched = ['inscripcion', 'espacio', 'anio_academico'];
  if (watched.includes(e.target?.name)) {
    // esperar un tick para que termine el update del DOM y luego reinyectar si hace falta
    setTimeout(function () { ensureEstadoOptions(false); }, 0);
  }
});

// 3) Si el DOM se actualiza por scripts (fetch/innerHTML/htmx/etc.)
new MutationObserver(function () {
  setTimeout(function () { ensureEstadoOptions(false); }, 50);
}).observe(document.getElementById('form-inscribir') || document.body, { childList: true, subtree: true });
// --- fin defensa ---
/* ------------------------------------------------------------------------- */

// Helpers para mostrar/ocultar campos de baja cuando cambia el "estado"
function toggleBajaFields(stateValue) {
  // Los campos vienen del form Django, así que ocultamos input y su label
  const fecha = document.querySelector('#id_fecha_baja');
  const motivo = document.querySelector('#id_motivo_baja');

  const fechaLabel = document.querySelector('label[for="id_fecha_baja"]');
  const motivoLabel = document.querySelector('label[for="id_motivo_baja"]');

  const show = (el, on) => { if (!el) return; el.style.display = on ? '' : 'none'; };

  const isBaja = String(stateValue || '').toUpperCase() === 'BAJA';
  show(fecha, isBaja);
  show(fechaLabel, isBaja);
  show(motivo, isBaja);
  show(motivoLabel, isBaja);

  // Si no es BAJA, limpiamos valores para no mandar basura
  if (!isBaja) {
    if (fecha) fecha.value = '';
    if (motivo) motivo.value = '';
  }
}

// Inicializa listeners de UI (solo si estamos en el form)
function initInscripcionUI() {
  const form = document.getElementById('form-inscribir');
  if (!form) return;

  const actionInput = form.querySelector('input[name="action"]');
  const action = (actionInput && actionInput.value) || '';

  // Solo aplica a la acción de inscribir a materia
  if (action !== 'insc_esp') return;

  // Hook de cambio de estado
  const estadoSel = form.querySelector('[name="estado"]') || document.getElementById('id_estado');
  if (estadoSel) {
    toggleBajaFields(estadoSel.value); // estado inicial
    estadoSel.addEventListener('change', (e) => toggleBajaFields(e.target.value));
  }
}

window.addEventListener('DOMContentLoaded', initInscripcionUI);

// Llamada AJAX para guardar la inscripción de cursada
// Llamada AJAX para guardar la inscripción de cursada
window.guardarInscripcion = async function() { // Ya no necesita el parámetro urlGuardar
  const form = document.getElementById('form-inscribir');
  if (!form) {
    alert('No se encontró el formulario de inscripción.');
    return;
  }

  // Verificación rápida de campos mínimos
  const insc = form.querySelector('[name="inscripcion"]');
  const anio = form.querySelector('[name="anio_academico"]');
  const esp  = form.querySelector('[name="espacio"]');
  const est  = form.querySelector('[name="estado"]');

  if (!insc || !anio || !esp || !est) {
    alert('Faltan campos requeridos en el formulario (inscripción, año, espacio, estado).');
    return;
  }

  // === LA LÓGICA NUEVA ===
  // Obtenemos el ID de la inscripción a carrera que el usuario seleccionó
  const inscripcionCarreraId = insc.value;
  if (!inscripcionCarreraId) {
      alert('Por favor, selecciona primero una inscripción a carrera.');
      return;
  }
  // Construimos la URL dinámicamente con ese ID
  const urlGuardar = `/panel/inscripciones/${inscripcionCarreraId}/cursadas/crear/`;
  // =======================

  const data = new FormData(form);

  // CSRF
  const csrf = getCookie('csrftoken') || getCsrfFromForm();

  try {
    const resp = await fetch(urlGuardar, { // Usamos la URL que acabamos de construir
      method: 'POST',
      headers: { 'X-CSRFToken': csrf },
      body: data,
      credentials: 'same-origin',
    });

    const json = await resp.json();

    if (!resp.ok || !json || json.ok !== true) {
      const msg = (json && (json.error || JSON.stringify(json.errors))) || ('HTTP ' + resp.status);
      throw new Error(msg);
    }

    alert('Guardado ✔');

    // Si quieres que la página se refresque después de guardar, puedes descomentar la siguiente línea:
    // location.reload();

  } catch (err) {
    console.error(err);
    alert('Error al guardar: ' + (err && err.message ? err.message : 'desconocido'));
  }
};


(function(){
  function ensureEstadoOptions(force){
    const root = document.getElementById('form-inscribir') || document;
    const sel = root.querySelector('[name="estado"]') || document.getElementById('id_estado');
    if (!sel) return;
    const needsFill = !sel.options || sel.options.length === 0;
    if (needsFill) {
      sel.innerHTML = '';
      sel.add(new Option('En curso','EN_CURSO'));
      sel.add(new Option('Baja','BAJA'));
    }
    if (force && sel.value !== 'EN_CURSO') sel.value = 'EN_CURSO';
  }

  // 1) al cargar
  document.addEventListener('DOMContentLoaded', function(){ ensureEstadoOptions(true); });

  // 2) ante CUALQUIER cambio/entrada en el form (captura), por si re-renderiza
  ['change','input'].forEach(evt => {
    document.addEventListener(evt, () => setTimeout(() => ensureEstadoOptions(false), 0), true);
  });

  // 3) si hay reemplazos de DOM (AJAX/innerHTML/templating)
  const target = document.getElementById('form-inscribir') || document.body;
  new MutationObserver(() => setTimeout(() => ensureEstadoOptions(false), 0))
    .observe(target, { childList: true, subtree: true });

  // 4) hooks para fetch/XMLHttpRequest/htmx (si las usás)
  if (window.fetch) {
    const _fetch = window.fetch;
    window.fetch = (...args) => _fetch(...args).then(r => (setTimeout(() => ensureEstadoOptions(false), 0), r));
  }
  if (window.XMLHttpRequest) {
    const _send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...a){
      this.addEventListener('loadend', () => setTimeout(() => ensureEstadoOptions(false), 0));
      return _send.apply(this, a);
    };
  }
  if (window.htmx) {
    document.body.addEventListener('htmx:afterSwap', () => ensureEstadoOptions(false));
  }

  // 5) log opcional para depurar
  // console.debug('ensureEstadoOptions listo');
})();