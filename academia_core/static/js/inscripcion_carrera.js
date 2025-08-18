// static/js/inscripcion_carrera.js
(function(){
  function qs(s, ctx){return (ctx||document).querySelector(s);}
  function qsa(s, ctx){return Array.from((ctx||document).querySelectorAll(s));}
  function show(el, on){ if(!el) return; el.style.display = on ? "" : "none"; }
  function isChecked(el){ return !!(el && ((el.type==="checkbox" && el.checked) || (el.value === "true"))); }
  function val(el){ return el ? (el.value || "") : ""; }
  function clear(el){ if(!el) return; if(el.tagName==="TEXTAREA"||el.tagName==="INPUT") el.value=""; }

  document.addEventListener("DOMContentLoaded", function(){
    const form = document.querySelector("form");
    if(!form) return;

    const selProf = qs('[name="profesorado"]', form);

    // checks
    const ch = {
      dni:   qs('[name="doc_dni_legalizado"]', form),
      med:   qs('[name="doc_cert_medico"]', form),
      foto:  qs('[name="doc_fotos_carnet"]', form),
      folio: qs('[name="doc_folios_oficio"]', form),

      sec:   qs('[name="doc_titulo_sec_legalizado"]', form),

      ter1:  qs('[name="doc_titulo_terciario_legalizado"]', form),
      ter2:  qs('[name="doc_titulo_terciario_universitario_legalizado"]', form),

      inc:   qs('[name="doc_incumbencias"]', form),
      tram:  qs('[name="titulo_en_tramite"]', form),

      adeu:  qs('[name="adeuda_materias"]', form),
      nota:  qs('[name="nota_compromiso"]', form),
    };

    const secOnly = qsa(".sec-only", form);
    const cdOnly  = qsa(".cd-only", form);

    const extra = document.getElementById("insc-prof-extra");
    const matAde = qs('[name="materias_adeudadas"]', form);
    const instOrg = qs('[name="institucion_origen"]', form);

    const chipLeg = document.getElementById("chip-legajo");
    const chipAdm = document.getElementById("chip-condicion");
    const notaDiv = document.getElementById("chk-nota");

    function esCD(){
      if(!selProf) return false;
      const opt = selProf.options[selProf.selectedIndex];
      if (!opt) return false;
      const t = (opt.text||"").toLowerCase();
      return t.includes("certificación docente") || t.includes("certificacion docente");
    }

    function toggleDocSets(){
      const cd = esCD();
      secOnly.forEach(el => show(el, !cd));
      cdOnly.forEach(el  => show(el, cd));

      if (cd){
        if (ch.sec) ch.sec.checked = false;
      }else{
        if (ch.ter1) ch.ter1.checked = false;
        if (ch.ter2) ch.ter2.checked = false;
        if (ch.inc) ch.inc.checked = false;
      }
    }

    function toggleAdeuda(){
      const on = isChecked(ch.adeu);
      show(extra, on);
      if(!on){ clear(matAde); clear(instOrg); }
    }

    function tituloTerciarioOK(){
      return isChecked(ch.ter1) || isChecked(ch.ter2);
    }

    function calcularEstado(){
      const baseOk = isChecked(ch.dni) && isChecked(ch.med) && isChecked(ch.foto) && isChecked(ch.folio);
      const cd = esCD();
      const tituloOk = cd ? (tituloTerciarioOK() && isChecked(ch.inc)) : isChecked(ch.sec);
      const leg_ok = baseOk && tituloOk && !isChecked(ch.tram);
      const cond = (leg_ok && !isChecked(ch.adeu)) ? "REGULAR" : "CONDICIONAL";

      if (chipLeg) chipLeg.textContent = leg_ok ? "COMPLETO" : "INCOMPLETO";
      if (chipAdm) chipAdm.textContent = cond;

      show(notaDiv, cond === "CONDICIONAL");
      if (cond !== "CONDICIONAL" && ch.nota){ ch.nota.checked = false; }
    }

    function updateAll(){
      toggleDocSets();
      toggleAdeuda();
      calcularEstado();
    }

    // Listeners
    [selProf, ch.dni, ch.med, ch.foto, ch.folio, ch.sec, ch.ter1, ch.ter2, ch.inc, ch.tram, ch.adeu, ch.nota, matAde, instOrg]
      .filter(Boolean)
      .forEach(el => el.addEventListener("change", updateAll));

    updateAll();
  });
})();