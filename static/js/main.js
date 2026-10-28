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
  searchToggle:    document.getElementById('searchToggle'),
  siteSearch:      document.getElementById('siteSearch'),
  searchInput:     document.getElementById('siteSearchInput'),
  searchStatus:    document.getElementById('searchStatus'),
  clearSearch:     document.getElementById('clearSearch'),
  favoritesToggle: document.getElementById('favoritesToggle'),
  cartToggle:      document.getElementById('cartToggle'),
  cartDialog:      document.getElementById('cartDialog'),
  cartItems:       document.getElementById('cartItems'),
  cartCount:       document.getElementById('cartCount'),
  cartTotal:       document.getElementById('cartTotal'),
  storeNotice:     document.getElementById('storeNotice'),
  productCards:    Array.from(document.querySelectorAll('[data-product-id]')),
};

const STORE_KEYS = {
  favorites: 'orodelsol:favorites',
  cart: 'orodelsol:cart',
};

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});

let favoriteIds = new Set(loadFavoriteIds());
let cart = loadCart();
let showingFavorites = false;
let noticeTimeout;

function readStoredValue(key, fallback) {
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : fallback;
  } catch (error) {
    console.warn(`No se pudo leer el almacenamiento local (${key}).`, error);
    return fallback;
  }
}

function loadFavoriteIds() {
  const stored = readStoredValue(STORE_KEYS.favorites, []);
  return Array.isArray(stored) ? stored.map(String) : [];
}

function loadCart() {
  const stored = readStoredValue(STORE_KEYS.cart, {});
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return {};

  return Object.fromEntries(
    Object.entries(stored).filter(([, item]) =>
      item && typeof item.name === 'string' &&
      Number.isFinite(item.price) && item.price >= 0 &&
      Number.isSafeInteger(item.quantity) && item.quantity > 0
    )
  );
}

function saveStoredValue(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.warn(`No se pudo guardar en el almacenamiento local (${key}).`, error);
    showStoreNotice('No se pudieron guardar tus cambios en este navegador.');
    return false;
  }
}

function showStoreNotice(message) {
  if (!DOM.storeNotice) return;
  DOM.storeNotice.textContent = message;
  DOM.storeNotice.hidden = false;
  window.clearTimeout(noticeTimeout);
  noticeTimeout = window.setTimeout(() => {
    DOM.storeNotice.hidden = true;
  }, 3500);
}

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
    DOM.menuToggle.setAttribute('aria-label', 'Cerrar menú');
  }

  const firstLink = DOM.sidebar.querySelector('.sidebar__close, a, button');
  if (firstLink) firstLink.focus();
}

function closeSidebar() {
  if (!DOM.sidebar || !DOM.sidebarOverlay || !DOM.sidebar.classList.contains('is-open')) return;

  DOM.sidebar.classList.remove('is-open');
  DOM.sidebarOverlay.classList.remove('is-open');
  DOM.sidebar.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';

  if (DOM.menuToggle) {
    DOM.menuToggle.setAttribute('aria-expanded', 'false');
    DOM.menuToggle.setAttribute('aria-label', 'Abrir menú');
    DOM.menuToggle.focus();
  }
}

function initSidebarLinks() {
  if (!DOM.sidebar) return;

  DOM.sidebar.addEventListener('click', (event) => {
    if (event.target.closest('a')) closeSidebar();
  });
}


/* ════════════════════════════════════════════════════════
   3. SCROLL REVEAL
   Anima los elementos con clase .reveal al entrar al viewport
   ════════════════════════════════════════════════════════ */
function initRevealOnScroll() {
  const elements = document.querySelectorAll('.reveal');
  if (!elements.length) return;

  if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    elements.forEach((element) => element.classList.add('is-visible'));
    return;
  }

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
   4. FALLBACK DE IMÁGENES
   Sustituye una imagen de catálogo que no carga por un recurso local.
   ════════════════════════════════════════════════════════ */
function initImageFallbacks() {
  document.querySelectorAll('img[data-image-fallback]').forEach((image) => {
    const showFallback = () => {
      const fallback = image.dataset.imageFallback;
      if (fallback && image.src !== new URL(fallback, document.baseURI).href) {
        image.src = fallback;
      } else {
        image.removeAttribute('data-image-fallback');
      }
    };

    image.addEventListener('error', showFallback);
    if (image.complete && image.naturalWidth === 0) showFallback();
  });
}

function updateProductFilters() {
  let visibleCount = 0;
  const query = DOM.searchInput ? normalizeSearchText(DOM.searchInput.value) : '';

  DOM.productCards.forEach((card) => {
    const matchesQuery = !query || normalizeSearchText(card.textContent).includes(query);
    const matchesFavorites = !showingFavorites || favoriteIds.has(card.dataset.productId);
    card.hidden = !(matchesQuery && matchesFavorites);
    if (!card.hidden) visibleCount += 1;
  });

  if (DOM.searchStatus) {
    if (showingFavorites && favoriteIds.size === 0) {
      DOM.searchStatus.textContent = 'Aún no tienes productos favoritos. Marca una joya con el corazón para guardarla.';
    } else if (query || showingFavorites) {
      DOM.searchStatus.textContent = `${visibleCount} ${visibleCount === 1 ? 'producto encontrado' : 'productos encontrados'}.`;
    } else {
      DOM.searchStatus.textContent = '';
    }
    DOM.searchStatus.hidden = !query && !showingFavorites;
  }
}

function normalizeSearchText(value) {
  return value
    .trim()
    .toLocaleLowerCase('es')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function renderFavoriteButtons() {
  DOM.productCards.forEach((card) => {
    const button = card.querySelector('[data-action="favorite"]');
    if (!button) return;
    const isFavorite = favoriteIds.has(card.dataset.productId);
    button.classList.toggle('is-active', isFavorite);
    button.textContent = isFavorite ? '♥' : '♡';
    button.setAttribute('aria-pressed', String(isFavorite));
    button.setAttribute(
      'aria-label',
      `${isFavorite ? 'Quitar' : 'Añadir'} ${card.querySelector('.product-card__name')?.textContent || 'producto'} ${isFavorite ? 'de' : 'a'} favoritos`
    );
  });
}

function getCartQuantity() {
  return Object.values(cart).reduce((total, item) => total + item.quantity, 0);
}

function renderCart() {
  if (!DOM.cartItems || !DOM.cartCount || !DOM.cartTotal || !DOM.cartToggle) return;

  DOM.cartItems.replaceChildren();
  const entries = Object.entries(cart);
  const quantity = getCartQuantity();
  let total = 0;

  DOM.cartCount.textContent = String(quantity);
  DOM.cartToggle.setAttribute('aria-label', `Abrir carrito; ${quantity} ${quantity === 1 ? 'producto' : 'productos'}`);

  if (!entries.length) {
    const empty = document.createElement('p');
    empty.className = 'cart-dialog__empty';
    empty.textContent = 'Tu carrito está vacío. Añade una joya para verla aquí.';
    DOM.cartItems.append(empty);
  }

  entries.forEach(([id, item]) => {
    total += item.price * item.quantity;
    const row = document.createElement('article');
    row.className = 'cart-item';

    const name = document.createElement('span');
    name.className = 'cart-item__name';
    name.textContent = item.name;

    const detail = document.createElement('span');
    detail.className = 'cart-item__detail';
    detail.textContent = `${item.quantity} × ${currencyFormatter.format(item.price)}`;

    const remove = document.createElement('button');
    remove.className = 'cart-item__remove';
    remove.type = 'button';
    remove.dataset.action = 'remove-from-cart';
    remove.dataset.productId = id;
    remove.textContent = 'Quitar';
    remove.setAttribute('aria-label', `Quitar ${item.name} del carrito`);

    row.append(name, detail, remove);
    DOM.cartItems.append(row);
  });

  DOM.cartTotal.textContent = currencyFormatter.format(total);
}

function toggleSearch(open) {
  if (!DOM.siteSearch || !DOM.searchToggle) return;
  DOM.siteSearch.hidden = !open;
  DOM.searchToggle.setAttribute('aria-expanded', String(open));
  if (open && DOM.searchInput) DOM.searchInput.focus();
}

function openDialog(dialog) {
  if (!dialog) return;
  if (typeof dialog.showModal === 'function') {
    if (!dialog.open) dialog.showModal();
  } else {
    showStoreNotice('Tu navegador no permite abrir el carrito en esta ventana.');
  }
}

function initStoreControls() {
  if (!DOM.siteSearch) return;

  renderFavoriteButtons();
  renderCart();
  updateProductFilters();

  if (DOM.searchToggle) {
    DOM.searchToggle.addEventListener('click', () => {
      if (!document.getElementById('productos')) {
        window.location.assign(`${DOM.searchToggle.dataset.homeUrl}?openSearch=1#productos`);
        return;
      }
      toggleSearch(DOM.siteSearch.hidden);
    });
  }

  if (DOM.searchInput) {
    DOM.searchInput.addEventListener('input', updateProductFilters);
    DOM.searchInput.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        DOM.searchInput.value = '';
        updateProductFilters();
        toggleSearch(false);
        DOM.searchToggle.focus();
      }
    });
  }

  DOM.siteSearch.addEventListener('submit', (event) => {
    event.preventDefault();
    updateProductFilters();
  });

  if (DOM.clearSearch) {
    DOM.clearSearch.addEventListener('click', () => {
      DOM.searchInput.value = '';
      updateProductFilters();
      DOM.searchInput.focus();
    });
  }

  if (DOM.favoritesToggle) {
    DOM.favoritesToggle.addEventListener('click', () => {
      if (!document.getElementById('productos')) {
        window.location.assign(`${DOM.favoritesToggle.dataset.homeUrl}?showFavorites=1#productos`);
        return;
      }
      showingFavorites = !showingFavorites;
      DOM.favoritesToggle.setAttribute('aria-pressed', String(showingFavorites));
      DOM.favoritesToggle.classList.toggle('is-active', showingFavorites);
      updateProductFilters();
      document.getElementById('productos')?.scrollIntoView({ behavior: 'smooth' });
      if (showingFavorites && DOM.siteSearch.hidden) toggleSearch(true);
    });
  }

  if (DOM.cartToggle) DOM.cartToggle.addEventListener('click', () => openDialog(DOM.cartDialog));

  document.querySelectorAll('[data-close-store-dialog]').forEach((button) => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });

  if (DOM.cartDialog) {
    DOM.cartDialog.addEventListener('click', (event) => {
      if (event.target === DOM.cartDialog) DOM.cartDialog.close();
    });
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-action]');
    if (button && button.dataset.action === 'favorite') {
      const card = button.closest('[data-product-id]');
      if (!card) return;
      const id = card.dataset.productId;
      if (favoriteIds.has(id)) favoriteIds.delete(id);
      else favoriteIds.add(id);
      const saved = saveStoredValue(STORE_KEYS.favorites, Array.from(favoriteIds));
      renderFavoriteButtons();
      updateProductFilters();
      if (saved) {
        showStoreNotice(favoriteIds.has(id) ? 'Producto guardado en favoritos.' : 'Producto eliminado de favoritos.');
      }
    } else if (button && button.dataset.action === 'add-to-cart') {
      const card = button.closest('[data-product-id]');
      if (!card) return;
      const id = card.dataset.productId;
      const item = cart[id] || {
        name: button.dataset.productName,
        price: Number(button.dataset.productPrice),
        quantity: 0,
      };
      item.quantity += 1;
      cart[id] = item;
      const saved = saveStoredValue(STORE_KEYS.cart, cart);
      renderCart();
      if (saved) showStoreNotice(`${item.name} añadido al carrito.`);
    } else if (button && button.dataset.action === 'remove-from-cart') {
      delete cart[button.dataset.productId];
      saveStoredValue(STORE_KEYS.cart, cart);
      renderCart();
    }

    const categoryLink = event.target.closest('[data-category-query]');
    if (categoryLink) {
      event.preventDefault();
      const query = categoryLink.dataset.categoryQuery;
      if (!document.getElementById('productos')) {
        window.location.assign(`${categoryLink.dataset.homeUrl}?q=${encodeURIComponent(query)}#productos`);
        return;
      }

      showingFavorites = false;
      DOM.searchInput.value = query;
      DOM.favoritesToggle?.classList.remove('is-active');
      DOM.favoritesToggle?.setAttribute('aria-pressed', 'false');
      toggleSearch(true);
      updateProductFilters();
      window.history.replaceState(null, '', '#productos');
      document.getElementById('productos').scrollIntoView({ behavior: 'smooth' });
    }

    const socialLink = event.target.closest('[data-social-link]');
    if (socialLink) {
      const destination = socialLink.dataset.socialUrl.trim();
      if (!destination) {
        event.preventDefault();
        showStoreNotice(`El enlace oficial de ${socialLink.dataset.socialName} está pendiente de configurar.`);
        return;
      }
      try {
        const url = new URL(destination);
        if (!['http:', 'https:'].includes(url.protocol)) throw new TypeError('Protocolo no permitido');
        socialLink.href = url.href;
        socialLink.target = '_blank';
        socialLink.rel = 'noopener noreferrer';
      } catch (error) {
        event.preventDefault();
        console.warn(`El enlace de ${socialLink.dataset.socialName} no es válido.`, error);
        showStoreNotice(`El enlace de ${socialLink.dataset.socialName} aún no está configurado correctamente.`);
      }
    }
  });

  const params = new URLSearchParams(window.location.search);
  if (params.get('openSearch') === '1') toggleSearch(true);
  if (params.get('showFavorites') === '1' && DOM.favoritesToggle) {
    showingFavorites = true;
    DOM.favoritesToggle.setAttribute('aria-pressed', 'true');
    DOM.favoritesToggle.classList.add('is-active');
    toggleSearch(true);
    updateProductFilters();
  }
  const initialQuery = params.get('q');
  if (initialQuery && DOM.searchInput) {
    DOM.searchInput.value = initialQuery;
    toggleSearch(true);
    updateProductFilters();
  }
}

function initPasswordVisibility() {
  const toggle = document.querySelector('[data-password-toggle]');
  if (!toggle) return;

  const password = document.getElementById(toggle.getAttribute('aria-controls'));
  if (!password) return;

  toggle.addEventListener('click', () => {
    const isVisible = password.type === 'text';
    password.type = isVisible ? 'password' : 'text';
    toggle.setAttribute('aria-label', isVisible ? 'Mostrar contraseña' : 'Ocultar contraseña');
    toggle.setAttribute('aria-pressed', String(!isVisible));
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
  initSidebarLinks();

  /* Tecla Escape cierra sidebar */
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeSidebar();
  });

  /* Mostrar u ocultar la contraseña del formulario de acceso */
  initPasswordVisibility();

  initImageFallbacks();
  initStoreControls();
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
