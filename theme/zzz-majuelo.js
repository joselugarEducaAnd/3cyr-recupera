/* ==========================================================================
   Estilo «IES El Majuelo» para eXeLearning 4 · zzz-majuelo.js
   Complemento de zzz-majuelo.css. eXe 4 copia al export y enlaza en cada
   página TODOS los .js de la raíz del tema, por orden alfabético: este se
   carga después de style.js (tema Base), que no se toca.
   Solo actúa en webs exportadas (body.exe-export): en el editor de eXe no
   hace nada, así que nada de lo que añade puede acabar guardado en el .elpx.
   ========================================================================== */

/* --------------------------------------------------------------------------
   2026-10-10 · DOCA-064 (DOCA-103) — pista visual en tablas desplazables
   - Marca con .mj-desliza solo las .tabla-datos que dejan CONTENIDO fuera de
     su caja (más que el relleno de la celda), lo que pasa bajo 1024 px por el
     ajuste del 2026-10-09 de zzz-majuelo.css.
   - Les antepone «Desliza para ver más columnas →» (aria-hidden: es una pista
     visual; el lector de pantalla ya recorre la tabla entera) y tabindex=0.
   - .mj-inicio / .mj-final dicen al CSS qué borde difuminar.
   - Se recalcula al cargar, al cambiar el tamaño de la ventana y cuando una
     tabla cambia de tamaño (pestañas, acordeones o cajas que se despliegan:
     una tabla oculta mide 0 y no se puede saber si desborda hasta que se ve).
   -------------------------------------------------------------------------- */
(function () {
  var TEXTO = 'Desliza para ver más columnas →';

  function esExport() {
    return !!(document.body && document.body.classList.contains('exe-export'));
  }

  function estado(t) {
    var max = t.scrollWidth - t.clientWidth;
    t.classList.toggle('mj-inicio', t.scrollLeft <= 1);
    t.classList.toggle('mj-final', t.scrollLeft >= max - 1);
  }

  // Lo que se esconde por la derecha solo es contenido si pasa del relleno de la
  // celda: una tabla que «desborda» 3 px solo oculta relleno y no lleva pista
  // (medido en 4.º TEC SdA 01 a 768 px: 2 tablas así, con el texto 10-13 px
  // dentro del borde).
  function relleno(t) {
    var c = t.querySelector('td, th');
    var r = c ? parseFloat(window.getComputedStyle(c).paddingRight) : 0;
    return isNaN(r) ? 0 : r;
  }

  function marcarTabla(t) {
    var desborda = t.scrollWidth - t.clientWidth > Math.max(1, relleno(t));
    var p = t.previousElementSibling;
    var tiene = !!(p && p.classList && p.classList.contains('mj-pista-desliza'));
    t.classList.toggle('mj-desliza', desborda);
    if (desborda && !tiene) {
      p = document.createElement('p');
      p.className = 'mj-pista-desliza';
      p.setAttribute('aria-hidden', 'true');
      p.textContent = TEXTO;
      t.parentNode.insertBefore(p, t);
      t.setAttribute('tabindex', '0');
    } else if (!desborda && tiene) {
      p.parentNode.removeChild(p);
      t.removeAttribute('tabindex');
    }
    estado(t);
  }

  var observador = null;
  if (typeof window.ResizeObserver === 'function') {
    observador = new ResizeObserver(function (entradas) {
      window.requestAnimationFrame(function () {
        entradas.forEach(function (e) { marcarTabla(e.target); });
      });
    });
  }

  function marcar() {
    if (!esExport()) return;
    var tablas = document.querySelectorAll('.exe-content table.tabla-datos');
    Array.prototype.forEach.call(tablas, function (t) {
      if (!t.getAttribute('data-mj-scroll')) {
        t.setAttribute('data-mj-scroll', '1');
        t.addEventListener('scroll', function () { estado(t); }, { passive: true });
        if (observador) observador.observe(t);
      }
      marcarTabla(t);
    });
  }

  var espera;
  window.addEventListener('load', marcar);
  window.addEventListener('resize', function () {
    clearTimeout(espera);
    espera = setTimeout(marcar, 150);
  });
  if (document.readyState === 'complete') marcar();
})();
