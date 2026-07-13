(() => {
  const toggle = document.querySelector('[data-nav-toggle]');
  const menu = document.querySelector('[data-nav-menu]');
  const setMenu = open => {
    toggle.setAttribute('aria-expanded', String(open));
    menu?.classList.toggle('is-open', open);
    document.body.classList.toggle('nav-is-open', open);
  };
  toggle?.addEventListener('click', () => {
    setMenu(toggle.getAttribute('aria-expanded') !== 'true');
  });
  menu?.addEventListener('click', event => {
    if (event.target.closest('a')) setMenu(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') {
      setMenu(false);
      toggle.focus();
    }
  });
  document.addEventListener('click', event => {
    if (toggle?.getAttribute('aria-expanded') === 'true' && !event.target.closest('[data-nav]')) setMenu(false);
  });

  const progress = document.querySelector('[data-progress]');
  if (progress) addEventListener('scroll', () => {
    const height = document.documentElement.scrollHeight - innerHeight;
    progress.style.width = `${height > 0 ? Math.min(100, scrollY / height * 100) : 0}%`;
  }, { passive: true });

  const search = document.querySelector('[data-article-search]');
  const cards = [...document.querySelectorAll('[data-article]')];
  const chips = [...document.querySelectorAll('[data-filter]')];
  let filter = 'all';
  const empty = document.querySelector('[data-filter-empty]');
  const count = document.querySelector('[data-result-count]');
  const refresh = () => {
    let visible = 0;
    cards.forEach(card => {
      const query = (search?.value || '').trim().toLowerCase();
      const matchesQuery = !query || card.dataset.title.includes(query) || card.textContent.toLowerCase().includes(query);
      const matchesType = filter === 'all' || card.dataset.type === filter;
      card.hidden = !(matchesQuery && matchesType);
      if (!card.hidden) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
    if (count) count.textContent = String(visible);
  };
  search?.addEventListener('input', refresh);
  chips.forEach(chip => chip.addEventListener('click', () => {
    filter = chip.dataset.filter;
    chips.forEach(item => item.classList.toggle('is-active', item === chip));
    refresh();
  }));
})();
