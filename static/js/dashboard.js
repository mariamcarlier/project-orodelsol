/* ═══════════════════════════════════════════════════════
   dashboard.js
   Responsabilidad: abrir y cerrar el menú lateral del panel
   en pantallas pequeñas (hamburguesa + fondo oscuro).
   ═══════════════════════════════════════════════════════ */

'use strict';

(function () {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('dashboardOverlay');
  const toggle = document.getElementById('menuToggle');
  if (!sidebar || !overlay || !toggle) return;

  const pantallaMovil = window.matchMedia('(max-width: 768px)');

  function setMenu(abierto, devolverFoco) {
    sidebar.classList.toggle('is-open', abierto);
    overlay.classList.toggle('is-open', abierto);
    document.body.classList.toggle('menu-open', abierto);
    toggle.setAttribute('aria-expanded', String(abierto));
    toggle.setAttribute('aria-label', abierto ? 'Cerrar menú' : 'Abrir menú');

    if (abierto) {
      const primero = sidebar.querySelector('a, summary, button');
      if (primero) primero.focus();
    } else if (devolverFoco) {
      toggle.focus();
    }
  }

  toggle.addEventListener('click', function () {
    setMenu(!sidebar.classList.contains('is-open'), true);
  });

  overlay.addEventListener('click', function () {
    setMenu(false, true);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
      setMenu(false, true);
    }
  });

  /* Si la ventana crece hasta escritorio con el menú abierto, se restablece. */
  pantallaMovil.addEventListener('change', function (evento) {
    if (!evento.matches) setMenu(false, false);
  if (sidebar && overlay && toggle) {
    const pantallaMovil = window.matchMedia('(max-width: 768px)');

    function setMenu(abierto, devolverFoco) {
      sidebar.classList.toggle('is-open', abierto);
      overlay.classList.toggle('is-open', abierto);
      document.body.classList.toggle('menu-open', abierto);
      toggle.setAttribute('aria-expanded', String(abierto));
      toggle.setAttribute('aria-label', abierto ? 'Cerrar menú' : 'Abrir menú');

      if (abierto) {
        const primero = sidebar.querySelector('a, summary, button');
        if (primero) primero.focus();
      } else if (devolverFoco) {
        toggle.focus();
      }
    }

    toggle.addEventListener('click', function () {
      setMenu(!sidebar.classList.contains('is-open'), true);
    });

    overlay.addEventListener('click', function () {
      setMenu(false, true);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
        setMenu(false, true);
      }
    });

    /* Si la ventana crece hasta escritorio con el menú abierto, se restablece. */
    pantallaMovil.addEventListener('change', function (evento) {
      if (!evento.matches) setMenu(false, false);
    });
  }

  document.addEventListener('click', function (event) {
    const opener = event.target.closest('[data-dashboard-dialog-open]');
    if (!opener) return;

    const dialog = document.getElementById(opener.dataset.dashboardDialogOpen);
    if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
  });

  document.querySelectorAll('[data-dashboard-dialog-autoshow]').forEach(function (dialog) {
    if (typeof dialog.showModal === 'function') dialog.showModal();
  });
})();