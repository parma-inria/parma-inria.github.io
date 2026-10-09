"use strict";

(() => {
  // Il menu resta utilizzabile anche senza JavaScript; su mobile abilitiamo il pulsante.
  function initializeNavigation() {
    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.getElementById("site-navigation");

    if (!menuButton || !navigation) return;

    menuButton.hidden = false;
    const mobileViewport = window.matchMedia("(max-width: 800px)");

    function setMenuOpen(open) {
      navigation.classList.toggle("is-open", open);
      menuButton.setAttribute("aria-expanded", String(open));
    }

    setMenuOpen(false);
    document.documentElement.classList.add("js");

    menuButton.addEventListener("click", () => {
      setMenuOpen(menuButton.getAttribute("aria-expanded") !== "true");
    });

    navigation.addEventListener("click", (event) => {
      if (mobileViewport.matches && event.target.closest("a")) {
        setMenuOpen(false);
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true") {
        setMenuOpen(false);
        menuButton.focus();
      }
    });

    mobileViewport.addEventListener("change", () => setMenuOpen(false));
  }

  // Ignoriamo maiuscole e accenti: "Gallouet" trova anche "Gallouët".
  function normalizeSearchText(value) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  // La ricerca esiste solo nella pagina dei membri: le altre pagine non vengono modificate.
  function initializeMemberSearch() {
    const searchInput = document.getElementById("member-search");
    const memberCount = document.getElementById("member-count");
    const memberCards = Array.from(document.querySelectorAll(".member-card[data-search]"));
    const memberSections = Array.from(document.querySelectorAll(".member-section"));
    const emptyState = document.querySelector(".empty-state");

    if (!searchInput || !memberCards.length) return;

    const toolbar = searchInput.closest(".members-toolbar");
    if (toolbar) toolbar.hidden = false;

    const searchableMembers = memberCards.map((card) => ({
      card,
      text: normalizeSearchText(card.dataset.search || card.textContent),
    }));

    function filterMembers() {
      const query = normalizeSearchText(searchInput.value.trim());
      const terms = query.split(/\s+/).filter(Boolean);
      let visibleCount = 0;

      // Tutte le parole cercate devono comparire nel nome, nell'affiliazione o nel ruolo.
      searchableMembers.forEach(({ card, text }) => {
        const visible = terms.every((term) => text.includes(term));
        card.hidden = !visible;
        if (visible) visibleCount += 1;
      });

      memberSections.forEach((section) => {
        const hasVisibleMember = Array.from(section.querySelectorAll(".member-card"))
          .some((card) => !card.hidden);
        // Senza ricerca lasciamo visibili tutti i gruppi, compresi gli ex membri.
        section.hidden = terms.length > 0 && !hasVisibleMember;
      });

      if (memberCount) {
        memberCount.textContent = terms.length
          ? `${visibleCount} of ${memberCards.length} members shown`
          : `${memberCards.length} members`;
      }
      if (emptyState) emptyState.hidden = visibleCount > 0;
    }

    searchInput.addEventListener("input", filterMembers);
    searchInput.addEventListener("search", filterMembers);
    filterMembers();
  }

  // Lo script viene caricato con "defer": il documento è già pronto.
  initializeNavigation();
  initializeMemberSearch();
})();
