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
window.guardarInscripcion = async function(urlGuardar) {
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

  const data = new FormData(form);

  // CSRF
  const csrf = getCookie('csrftoken') || getCsrfFromForm();

  try {
    const resp = await fetch(urlGuardar, {
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

    // Si querés refrescar la lista/estado del form:
    // location.reload();

  } catch (err) {
    console.error(err);
    alert('Error al guardar: ' + (err && err.message ? err.message : 'desconocido'));
  }
};
