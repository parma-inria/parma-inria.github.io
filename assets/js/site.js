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
        // Templates come from the English catalogue and its generated translations.
        const template = terms.length
          ? memberCount.dataset.filteredTemplate
          : memberCount.dataset.countTemplate;
        memberCount.textContent = template
          .replaceAll("{visible}", String(visibleCount))
          .replaceAll("{total}", String(memberCards.length))
          .replaceAll("{count}", String(memberCards.length));
      }

      if (emptyState) emptyState.hidden = visibleCount > 0;
    }

    searchInput.addEventListener("input", filterMembers);
    searchInput.addEventListener("search", filterMembers);
    filterMembers();
  }

  // Annual agenda links reveal the matching archived programme and keep its URL shareable.
  function initializeSeminarCalendar() {
    if (!document.querySelector(".seminar-calendar")) return;

    function revealCalendarTarget() {
      const id = window.location.hash.slice(1);
      if (id !== "schedule-title" && !/^session-\d{4}-\d{2}-\d{2}$/.test(id)) return;
      const session = document.getElementById(id);
      if (!session) return;
      const archive = session.closest("details");
      if (archive) archive.open = true;
      // Native fragment scrolling and scripted scrolling must use the same offset.
      const header = document.querySelector(".site-header");
      document.documentElement.style.scrollPaddingTop = `${(header?.offsetHeight || 0) + 16}px`;
      window.requestAnimationFrame(() => {
        session.scrollIntoView({ block: "start" });
        session.focus({ preventScroll: true });
      });
    }

    window.addEventListener("hashchange", revealCalendarTarget);
    document.querySelectorAll(".schedule-link").forEach((link) => {
      link.addEventListener("click", () => {
        // Clicking the same date twice does not emit another hashchange.
        if (window.location.hash === link.hash) revealCalendarTarget();
      });
    });
    revealCalendarTarget();
  }

  // iOS can subscribe through webcal; other platforms use the provider chooser.
  function initializeCalendarSubscriptions() {
    const dialog = document.getElementById("calendar-subscription");
    if (!dialog || typeof dialog.showModal !== "function") return;

    const input = dialog.querySelector("#calendar-subscription-url");
    const status = dialog.querySelector(".calendar-copy-status");
    let opener = null;
    const opensAppleCalendar = /iPad|iPhone|iPod/.test(navigator.userAgent)
      || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

    document.querySelectorAll("[data-calendar-subscribe]").forEach((link) => {
      link.addEventListener("click", (event) => {
        // Let iOS follow the native subscription link. Keep the chooser ready
        // behind the app prompt so returning to the browser offers alternatives.
        if (!opensAppleCalendar) event.preventDefault();
        opener = link;
        input.value = link.dataset.feedUrl;
        dialog.querySelector("[data-calendar-native]").href = link.href;
        dialog.querySelector("[data-calendar-selection]").textContent = link.dataset.calendarTitle;
        dialog.querySelector("[data-calendar-scope]").textContent = link.dataset.calendarScope;
        status.textContent = "";
        dialog.showModal();
      });
    });

    dialog.addEventListener("close", () => opener?.focus({ preventScroll: true }));
    dialog.addEventListener("keydown", (event) => {
      if (event.key !== "Tab") return;
      const controls = [...dialog.querySelectorAll("a[href], button, input")]
        .filter((control) => !control.disabled && control.getClientRects().length);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    dialog.querySelector("[data-calendar-copy]").addEventListener("click", async () => {
      const value = input.value;
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(value);
        if (input.value === value) status.textContent = dialog.dataset.copySuccess;
      } catch {
        // Selecting the complete URL also works in local previews and restricted browsers.
        if (input.value !== value) return;
        input.focus();
        input.select();
        status.textContent = dialog.dataset.copyFallback;
      }
    });
  }

  // Startup: the deferred script runs after the page markup has been parsed.
  initializeNavigation();
  initializeMemberPortraits();
  initializeMemberSearch();
  initializeSeminarCalendar();
  initializeCalendarSubscriptions();
})();
