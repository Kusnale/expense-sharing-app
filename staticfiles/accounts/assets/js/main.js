/**
 * Groovin (trimmed + defensive) main.js
 * - Guards against missing DOM nodes to avoid "Cannot read properties of null"
 * - Supports both #navmenu (original) and #navbar (your template)
 * - Only initialises vendor features if corresponding libs / elements exist
 */

(function() {
  "use strict";

  // --- small helpers ---
  const qs = (s, root = document) => root.querySelector(s);
  const qsa = (s, root = document) => Array.from(root.querySelectorAll(s || ""));
  const safeOn = (el, ev, fn) => { if (el && typeof el.addEventListener === 'function') el.addEventListener(ev, fn); };

  // --- toggled class on scroll (only if header exists) ---
  function toggleScrolled() {
    const selectBody = qs('body');
    const selectHeader = qs('#header');
    if (!selectHeader) return;
    // only apply if header uses a sticky/fixed class (keeps original logic)
    if (!selectHeader.classList.contains('scroll-up-sticky') &&
        !selectHeader.classList.contains('sticky-top') &&
        !selectHeader.classList.contains('fixed-top')) return;
    window.scrollY > 100 ? selectBody.classList.add('scrolled') : selectBody.classList.remove('scrolled');
  }
  safeOn(document, 'scroll', toggleScrolled);
  safeOn(window, 'load', toggleScrolled);

  // --- Mobile nav toggle ---
  const mobileNavToggleBtn = qs('.mobile-nav-toggle');
  function mobileNavToogle() {
    const body = qs('body');
    if (!body || !mobileNavToggleBtn) return;
    body.classList.toggle('mobile-nav-active');
    mobileNavToggleBtn.classList.toggle('bi-list');
    mobileNavToggleBtn.classList.toggle('bi-x');
  }
  safeOn(mobileNavToggleBtn, 'click', mobileNavToogle);

  // --- Hide mobile nav on same-page/hash links ---
  // support both selectors: #navmenu and #navbar and generic .navmenu/.navbar links
  const navLinkSelectors = ['#navmenu a', '#navbar a', '.navmenu a', '.navbar a'];
  navLinkSelectors.forEach(sel => {
    qsa(sel).forEach(navmenu => {
      safeOn(navmenu, 'click', () => {
        if (qs('.mobile-nav-active')) {
          mobileNavToogle();
        }
      });
    });
  });

  // --- Toggle mobile nav dropdowns (if present) ---
  ['.navmenu .toggle-dropdown', '.navbar .toggle-dropdown'].forEach(sel => {
    qsa(sel).forEach(navmenu => {
      safeOn(navmenu, 'click', function(e) {
        e.preventDefault();
        if (this.parentNode) this.parentNode.classList.toggle('active');
        if (this.parentNode && this.parentNode.nextElementSibling) this.parentNode.nextElementSibling.classList.toggle('dropdown-active');
        e.stopImmediatePropagation();
      });
    });
  });

  // --- Preloader ---
  const preloader = qs('#preloader');
  if (preloader) {
    safeOn(window, 'load', () => {
      preloader.remove();
    });
  }

  // --- Scroll top button ---
  let scrollTop = qs('.scroll-top');
  function toggleScrollTop() {
    if (!scrollTop) return;
    window.scrollY > 100 ? scrollTop.classList.add('active') : scrollTop.classList.remove('active');
  }
  if (scrollTop) {
    safeOn(scrollTop, 'click', (e) => {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    safeOn(window, 'load', toggleScrollTop);
    safeOn(document, 'scroll', toggleScrollTop);
  }

  // --- AOS (if loaded) ---
  function aosInit() {
    if (typeof AOS !== 'undefined' && AOS.init) {
      AOS.init({ duration: 600, easing: 'ease-in-out', once: true, mirror: false });
    }
  }
  safeOn(window, 'load', aosInit);

  // --- Auto generate carousel indicators (guarded) ---
  qsa('.carousel-indicators').forEach((carouselIndicator) => {
    const carousel = carouselIndicator.closest('.carousel');
    if (!carousel) return;
    const items = qsa('.carousel-item', carousel);
    items.forEach((carouselItem, index) => {
      const id = carousel.id || `carousel-${index}`;
      // ensure carousel has an id (used by indicators)
      if (!carousel.id) carousel.id = id;
      if (index === 0) {
        carouselIndicator.innerHTML += `<li data-bs-target="#${carousel.id}" data-bs-slide-to="${index}" class="active"></li>`;
      } else {
        carouselIndicator.innerHTML += `<li data-bs-target="#${carousel.id}" data-bs-slide-to="${index}"></li>`;
      }
    });
  });

  // --- PureCounter (if present) ---
  if (typeof PureCounter !== 'undefined') {
    try { new PureCounter(); } catch (err) { /* ignore */ }
  }

  // --- GLightbox (if present) ---
  if (typeof GLightbox !== 'undefined') {
    try { GLightbox({ selector: '.glightbox' }); } catch (err) { /* ignore */ }
  }

  // --- Isotope + imagesLoaded (if present and elements exist) ---
  qsa('.isotope-layout').forEach(function(isotopeItem) {
    if (typeof imagesLoaded === 'undefined' || typeof Isotope === 'undefined') return;
    const container = qs('.isotope-container', isotopeItem);
    if (!container) return;
    let layout = isotopeItem.getAttribute('data-layout') ?? 'masonry';
    let filter = isotopeItem.getAttribute('data-default-filter') ?? '*';
    let sort = isotopeItem.getAttribute('data-sort') ?? 'original-order';
    let initIsotope;
    try {
      imagesLoaded(container, function() {
        initIsotope = new Isotope(container, { itemSelector: '.isotope-item', layoutMode: layout, filter: filter, sortBy: sort });
      });
      qsa('.isotope-filters li', isotopeItem).forEach(function(filters) {
        safeOn(filters, 'click', function() {
          const active = qs('.isotope-filters .filter-active', isotopeItem);
          if (active) active.classList.remove('filter-active');
          this.classList.add('filter-active');
          if (initIsotope && initIsotope.arrange) {
            initIsotope.arrange({ filter: this.getAttribute('data-filter') });
          }
          if (typeof aosInit === 'function') aosInit();
        });
      });
    } catch (err) { /* fail silently if libs missing */ }
  });

  // --- FAQ toggle ---
  qsa('.faq-item h3, .faq-item .faq-toggle').forEach((faqItem) => {
    safeOn(faqItem, 'click', () => {
      if (faqItem.parentNode) faqItem.parentNode.classList.toggle('faq-active');
    });
  });

  // --- Swiper init (if present) ---
  function initSwiper() {
    if (typeof Swiper === 'undefined') return;
    qsa(".init-swiper").forEach(function(swiperElement) {
      try {
        const cfgEl = qs(".swiper-config", swiperElement);
        if (!cfgEl) return;
        let config = JSON.parse(cfgEl.innerHTML.trim());
        if (swiperElement.classList.contains("swiper-tab")) {
          // if custom pagination helper exists, call it
          if (typeof initSwiperWithCustomPagination === 'function') {
            initSwiperWithCustomPagination(swiperElement, config);
          } else {
            new Swiper(swiperElement, config);
          }
        } else {
          new Swiper(swiperElement, config);
        }
      } catch (err) { /* ignore json/initialisation errors */ }
    });
  }
  safeOn(window, 'load', initSwiper);

  // --- Correct scroll for anchor on load (if hash exists) ---
  safeOn(window, 'load', function() {
    if (window.location.hash) {
      const section = qs(window.location.hash);
      if (!section) return;
      setTimeout(() => {
        const scrollMarginTop = getComputedStyle(section).scrollMarginTop || '0px';
        window.scrollTo({ top: section.offsetTop - parseInt(scrollMarginTop || '0'), behavior: 'smooth' });
      }, 100);
    }
  });

  // --- Navmenu scrollspy (supports .navmenu and .navbar links that point to in-page sections) ---
  let navmenulinks = qsa('.navmenu a, .navbar a');
  function navmenuScrollspy() {
    if (!navmenulinks.length) return;
    navmenulinks.forEach(navmenulink => {
      try {
        if (!navmenulink.hash) return;
        let section = qs(navmenulink.hash);
        if (!section) return;
        let position = window.scrollY + 200;
        if (position >= section.offsetTop && position <= (section.offsetTop + section.offsetHeight)) {
          qsa('.navmenu a.active, .navbar a.active').forEach(link => link.classList.remove('active'));
          navmenulink.classList.add('active');
        } else {
          navmenulink.classList.remove('active');
        }
      } catch (err) { /* ignore */ }
    });
  }
  safeOn(window, 'load', navmenuScrollspy);
  safeOn(document, 'scroll', navmenuScrollspy);

})();

function showToast(message, type='success') {
    const toastEl = document.getElementById('globalToast');
    const toastMsg = document.getElementById('toastMessage');
    
    if (toastEl && toastMsg) {
        toastMsg.textContent = message;
        toastEl.className = `toast align-items-center text-white bg-${type} border-0`;
        var bsToast = new bootstrap.Toast(toastEl, { autohide: true, delay: 2000 }); // 2 sec
        bsToast.show();
    }
}
