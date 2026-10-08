"use strict";

(() => {
  const menuButton = document.querySelector(".menu-toggle");
  const navigation = document.getElementById("site-navigation");

  if (menuButton && navigation) {
    menuButton.hidden = false;
    const mobileViewport = window.matchMedia("(max-width: 800px)");
    const setMenuOpen = (open) => {
      navigation.classList.toggle("is-open", open);
      menuButton.setAttribute("aria-expanded", String(open));
    };

    setMenuOpen(false);
    document.documentElement.classList.add("js");

    menuButton.addEventListener("click", () => {
      setMenuOpen(menuButton.getAttribute("aria-expanded") !== "true");
    });

    navigation.addEventListener("click", (event) => {
      if (mobileViewport.matches && event.target.closest("a")) setMenuOpen(false);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && menuButton.getAttribute("aria-expanded") === "true") {
        setMenuOpen(false);
        menuButton.focus();
      }
    });

    mobileViewport.addEventListener("change", () => setMenuOpen(false));
  }

  const searchInput = document.getElementById("member-search");
  const memberCount = document.getElementById("member-count");
  const memberCards = Array.from(document.querySelectorAll(".member-card[data-search]"));
  const memberSections = Array.from(document.querySelectorAll(".member-section"));
  const emptyState = document.querySelector(".empty-state");

  if (searchInput && memberCards.length) {
    const toolbar = searchInput.closest('.members-toolbar');
    if (toolbar) toolbar.hidden = false;
    const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const searchableMembers = memberCards.map((card) => ({
      card,
      text: normalize(card.dataset.search || card.textContent),
    }));

    const filterMembers = () => {
      const query = normalize(searchInput.value.trim());
      const terms = query.split(/\s+/).filter(Boolean);
      let visibleCount = 0;

      searchableMembers.forEach(({ card, text }) => {
        const visible = terms.every((term) => text.includes(term));
        card.hidden = !visible;
        if (visible) visibleCount += 1;
      });

      memberSections.forEach((section) => {
        const hasVisibleMember = Array.from(section.querySelectorAll(".member-card")).some((card) => !card.hidden);
        section.hidden = terms.length > 0 && !hasVisibleMember;
      });

      if (memberCount) {
        memberCount.textContent = terms.length
          ? `${visibleCount} of ${memberCards.length} members shown`
          : `${memberCards.length} members`;
      }
      if (emptyState) emptyState.hidden = visibleCount > 0;
    };

    searchInput.addEventListener("input", filterMembers);
    searchInput.addEventListener("search", filterMembers);
    filterMembers();
  }
})();
