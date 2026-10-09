"use strict";

(() => {
  // Navigation: enable the mobile button while keeping links usable without JavaScript.
  function initializeNavigation() {
    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.getElementById("site-navigation");

    if (!menuButton || !navigation) return;

    menuButton.hidden = false;
    const mobileViewport = window.matchMedia("(max-width: 800px)");

    // Keep the visual state and the accessibility state in sync.
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

  // Search normalization: ignore case and accents, so "Gallouet" also finds "Gallouët".
  function normalizeSearchText(value) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  // Member portraits: keep the initials visible until a remote or local image has loaded.
  function initializeMemberPortraits() {
    document.querySelectorAll(".member-portrait").forEach((image) => {
      function updatePortrait() {
        image.classList.toggle("is-loaded", image.complete && image.naturalWidth > 0);
      }

      image.addEventListener("load", updatePortrait);
      image.addEventListener("error", () => image.classList.remove("is-loaded"));

      // Cached images may have finished loading before the listeners were added.
      updatePortrait();
    });
  }

  // Member search: initialize this feature only when the team page contains a search field.
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

      // Every search term must appear in the name, affiliation or member group.
      searchableMembers.forEach(({ card, text }) => {
        const visible = terms.every((term) => text.includes(term));
        card.hidden = !visible;
        if (visible) visibleCount += 1;
      });

      memberSections.forEach((section) => {
        const hasVisibleMember = Array.from(section.querySelectorAll(".member-card"))
          .some((card) => !card.hidden);

        // An empty search keeps every group visible, including former members.
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

  // Startup: the deferred script runs after the page markup has been parsed.
  initializeNavigation();
  initializeMemberPortraits();
  initializeMemberSearch();
})();
