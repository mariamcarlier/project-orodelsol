/* ═══════════════════════════════════════════════════════
   main.js
   Responsabilidad: Comportamiento e interacción
   Reglas:
   - Sin código inline en HTML (no onclick="...")
   - Cada función tiene UNA sola responsabilidad
   - Los elementos del DOM se obtienen UNA sola vez
   ═══════════════════════════════════════════════════════ */

'use strict';

/* ────────────────────────────────────────────────────────
   REFERENCIAS AL DOM
   Se obtienen una sola vez al cargar la página
   ──────────────────────────────────────────────────────── */
const DOM = {
  siteHeader:      document.getElementById('siteHeader'),
  categoryBar:     document.getElementById('categoryBar'),
  sidebar:         document.getElementById('sidebar'),
  sidebarOverlay:  document.getElementById('sidebarOverlay'),
  menuToggle:      document.getElementById('menuToggle'),
  sidebarClose:    document.getElementById('sidebarClose'),
  announceBar:     document.getElementById('announceBar'),
  cartCount:       document.getElementById('cartCount'),
};

/* ─── Umbrales de scroll ─── */
const SCROLL = {
  COMPACT:  80,   /* header se compacta */
  HIDE_NAV: 120,  /* barra de categorías se oculta */
};


/* ════════════════════════════════════════════════════════
   1. HEADER SCROLL
   Compacta el header y oculta la barra de categorías
   ════════════════════════════════════════════════════════ */
function handleHeaderScroll() {
  const scrollY = window.scrollY;

  /* Header compacto */
  if (DOM.siteHeader) {
    DOM.siteHeader.classList.toggle('is-compact', scrollY > SCROLL.COMPACT);
  }

  /* Barra de categorías oculta */
  if (DOM.categoryBar) {
    DOM.categoryBar.classList.toggle('is-hidden', scrollY > SCROLL.HIDE_NAV);
  }
}


/* ════════════════════════════════════════════════════════
   2. SIDEBAR
   Abre y cierra el menú lateral
   ════════════════════════════════════════════════════════ */
function openSidebar() {
  if (!DOM.sidebar || !DOM.sidebarOverlay) return;

  DOM.sidebar.classList.add('is-open');
  DOM.sidebarOverlay.classList.add('is-open');
  DOM.sidebar.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden'; /* evita scroll de fondo */

  /* Actualiza aria del botón de menú */
  if (DOM.menuToggle) {
    DOM.menuToggle.setAttribute('aria-expanded', 'true');
  }
}

function closeSidebar() {
  if (!DOM.sidebar || !DOM.sidebarOverlay) return;

  DOM.sidebar.classList.remove('is-open');
  DOM.sidebarOverlay.classList.remove('is-open');
  DOM.sidebar.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';

  if (DOM.menuToggle) {
    DOM.menuToggle.setAttribute('aria-expanded', 'false');
  }
}


/* ════════════════════════════════════════════════════════
   3. SCROLL REVEAL
   Anima los elementos con clase .reveal al entrar al viewport
   ════════════════════════════════════════════════════════ */
function initRevealOnScroll() {
  const elements = document.querySelectorAll('.reveal');
  if (!elements.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target); /* se revela una sola vez */
        }
      });
    },
    { threshold: 0.1 }
  );

  elements.forEach((el) => observer.observe(el));
}


/* ════════════════════════════════════════════════════════
   4. ANNOUNCE BAR - barra de anuncios
   Rota mensajes automáticamente con fade
   ════════════════════════════════════════════════════════ */
const ANNOUNCE_MESSAGES = [
  '✦ Certificado de autenticidad en Oro 18K incluido en cada compra ✦',
  '🚚 Envío gratis en compras superiores a $200.000 ✦',
  '✦ 10% de descuento en tu primera compra — Código: PRIMERA10 ✦',
  '⭐ Más de 500 familias confían en Joyas Oro del Sol ✦',
];

let announceIndex = 0;

function rotateAnnounceBar() {
  if (!DOM.announceBar) return;

  DOM.announceBar.style.opacity = '0';

  setTimeout(() => {
    announceIndex = (announceIndex + 1) % ANNOUNCE_MESSAGES.length;
    DOM.announceBar.textContent = ANNOUNCE_MESSAGES[announceIndex];
    DOM.announceBar.style.opacity = '1';
  }, 400);
}


/* ════════════════════════════════════════════════════════
   5. FAVORITOS
   Maneja el toggle de corazón en product cards
   ════════════════════════════════════════════════════════ */
function handleFavToggle(button) {
  const isActive = button.classList.contains('is-active');

  if (isActive) {
    button.classList.remove('is-active');
    button.textContent = '♡';
    button.setAttribute('aria-label', 'Añadir a favoritos');
  } else {
    button.classList.add('is-active');
    button.textContent = '♥';
    button.setAttribute('aria-label', 'Quitar de favoritos');
  }
}


/* ════════════════════════════════════════════════════════
   6. CARRITO (placeholder — conectar con backend)
   ════════════════════════════════════════════════════════ */
let cartItems = 2; /* simulado */

function addToCart(productId) {
  cartItems += 1;
  updateCartBadge();
  console.log(`Producto ${productId} añadido al carrito`);
  /* Aquí irá la llamada real al backend o Context API */
}

function updateCartBadge() {
  if (DOM.cartCount) {
    DOM.cartCount.textContent = cartItems;
  }
}


/* ════════════════════════════════════════════════════════
   7. DELEGACIÓN DE EVENTOS
   Un solo listener por contenedor — más eficiente
   que un listener por botón
   ════════════════════════════════════════════════════════ */
function initProductCardEvents() {
  /* Escucha todos los clicks dentro del main */
  const main = document.getElementById('mainContent');
  if (!main) return;

  main.addEventListener('click', (event) => {
    const target = event.target;

    /* Botón de favorito */
    if (target.dataset.action === 'fav') {
      handleFavToggle(target);
      return;
    }

    /* Barra de añadir al carrito */
    if (target.classList.contains('product-card__bar')) {
      const card = target.closest('[data-id]');
      const productId = card ? card.dataset.id : 'unknown';
      addToCart(productId);
      return;
    }
  });
}


/* ════════════════════════════════════════════════════════
   8. EVENTOS GLOBALES
   Se registran aquí — nunca como atributos onclick en HTML
   ════════════════════════════════════════════════════════ */
function initEvents() {
  /* Scroll */
  window.addEventListener('scroll', handleHeaderScroll, { passive: true });

  /* Sidebar */
  if (DOM.menuToggle)   DOM.menuToggle.addEventListener('click', openSidebar);
  if (DOM.sidebarClose) DOM.sidebarClose.addEventListener('click', closeSidebar);
  if (DOM.sidebarOverlay) DOM.sidebarOverlay.addEventListener('click', closeSidebar);

  /* Tecla Escape cierra sidebar */
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeSidebar();
  });

  /* Rotación de anuncios */
  setInterval(rotateAnnounceBar, 4500);

  /* Eventos de product cards (delegación) */
  initProductCardEvents();
}


/* ════════════════════════════════════════════════════════
   INIT — Punto de entrada único
   Todo se inicializa aquí cuando el DOM está listo
   ════════════════════════════════════════════════════════ */
function init() {
  initRevealOnScroll();
  initEvents();

  /* Estado inicial del scroll (por si la página carga a mitad) */
  handleHeaderScroll();
}

/* DOMContentLoaded garantiza que el HTML ya está parseado */
document.addEventListener('DOMContentLoaded', init);
