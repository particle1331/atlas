document.addEventListener("DOMContentLoaded", () => {
  const listing = document.getElementById("listing-listing");
  const list = window["quarto-listings"]?.["listing-listing"];
  const sidebar = document.getElementById("quarto-margin-sidebar");
  if (!listing || !list || !sidebar) return;

  const search = listing.querySelector(".quarto-listing-filter input");
  if (search) {
    search.placeholder = "Search titles…";
    search.setAttribute("aria-label", "Search posts by title");
  }

  // Read the displayed ISO dates so archive months match the dates in the table.
  const dates = new Map();
  const years = new Map();
  for (const item of list.items) {
    const date = item.values()["listing-date"]?.match(/^(\d{4})-(\d{2})-/);
    if (!date) continue;
    const [, year, month] = date;
    dates.set(item, { year, month });
    if (!years.has(year)) years.set(year, new Map());
    const months = years.get(year);
    months.set(month, (months.get(month) || 0) + 1);
  }
  if (!years.size) return;

  let selectedYear = null;
  let selectedMonth = null;
  const orderedYears = [...years.keys()].sort().reverse();
  const controls = [];

  // List.js has one filter predicate. Keep Quarto's category predicate and
  // combine it with the selected date; its title search remains independent.
  const filter = list.filter.bind(list);
  let categoryFilter = null;
  if (list.filtered) {
    const categoryItems = new Set(list.items.filter((item) => item.filtered));
    categoryFilter = (item) => categoryItems.has(item);
  }
  const applyFilters = () => {
    if (!categoryFilter && !selectedYear) return filter();
    return filter((item) => {
      if (categoryFilter && !categoryFilter(item)) return false;
      if (!selectedYear) return true;
      const date = dates.get(item);
      return date?.year === selectedYear &&
        (!selectedMonth || date.month === selectedMonth);
    });
  };
  list.filter = (predicate) => {
    categoryFilter = predicate;
    return applyFilters();
  };

  const container = document.createElement("section");
  container.className = "df-container";
  container.setAttribute("aria-labelledby", "posts-date-filter-title");
  const heading = document.createElement("h5");
  heading.id = "posts-date-filter-title";
  heading.className = "df-title";
  heading.textContent = "Date";
  container.append(heading);

  const makeButton = (label, count, className, onClick) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.append(document.createTextNode(label + " "));
    const total = document.createElement("span");
    total.className = "quarto-category-count";
    total.textContent = `(${count})`;
    button.append(total);
    button.addEventListener("click", onClick);
    return button;
  };

  const update = (filterResults = true) => {
    for (const { button, year, month, section } of controls) {
      const active = selectedYear === year && selectedMonth === month;
      button.classList.toggle("df-active", active);
      button.setAttribute("aria-pressed", String(active));
      if (section) {
        const expanded = year === (selectedYear || orderedYears[0]);
        section.classList.toggle("df-expanded", expanded);
        button.setAttribute("aria-expanded", String(expanded));
      }
    }
    if (filterResults) applyFilters();
  };

  const allDates = makeButton("All dates", list.items.length, "df-all-pill", () => {
    selectedYear = null;
    selectedMonth = null;
    update();
  });
  controls.push({ button: allDates, year: null, month: null });
  container.append(allDates);

  const monthFormat = new Intl.DateTimeFormat("en", {
    month: "long", timeZone: "UTC",
  });
  for (const year of orderedYears) {
    const months = years.get(year);
    const section = document.createElement("div");
    section.className = "df-year-section";
    const count = [...months.values()].reduce((sum, value) => sum + value, 0);
    const yearButton = makeButton(year, count, "df-year-pill", () => {
      selectedYear = selectedYear === year && !selectedMonth ? null : year;
      selectedMonth = null;
      update();
    });
    const chevron = document.createElement("span");
    chevron.className = "df-chevron";
    chevron.textContent = "›";
    chevron.setAttribute("aria-hidden", "true");
    yearButton.prepend(chevron);
    const monthList = document.createElement("div");
    monthList.id = `posts-months-${year}`;
    monthList.className = "df-months";
    yearButton.setAttribute("aria-controls", monthList.id);
    controls.push({ button: yearButton, year, month: null, section });
    for (const month of [...months.keys()].sort().reverse()) {
      const label = monthFormat.format(new Date(Date.UTC(2000, Number(month) - 1, 1)));
      const button = makeButton(label, months.get(month), "df-month-pill", () => {
        selectedMonth = selectedYear === year && selectedMonth === month ? null : month;
        selectedYear = year;
        update();
      });
      button.setAttribute("aria-label", `${label} ${year}`);
      controls.push({ button, year, month });
      monthList.append(button);
    }
    section.append(yearButton, monthList);
    container.append(section);
  }

  sidebar.prepend(container);
  update(false);
});
