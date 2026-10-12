htmx.config.historyRestoreAsHxRequest = false;
function syncFilters() {
  const params = new URLSearchParams(location.search);
  const form = document.querySelector('form');
  if (!form) return;
  for (const name of ['q', 'category', 'date', 'sort']) {
    const field = form.elements.namedItem(name);
    if (!field) continue;
    const fallback = name === 'sort' ? 'name' : name === 'date' ? field.defaultValue : '';
    field.value = params.get(name) || fallback;
    if (field.tagName === 'SELECT') {
      for (const option of field.options) {
        option.toggleAttribute('selected', option.value === field.value);
      }
    } else {
      field.setAttribute('value', field.value);
    }
  }
}
document.addEventListener('htmx:pushedIntoHistory', syncFilters);
document.addEventListener('htmx:historyRestore', syncFilters);
document.addEventListener('click', (event) => {
  if (event.target.closest('#close-preview')) {
    document.getElementById('preview').close();
    document.getElementById('preview-content').replaceChildren();
    return;
  }
  const link = event.target.closest('.preview-link');
  if (!link) return;
  event.preventDefault();
  const content = document.getElementById('preview-content');
  const image = new Image();
  image.alt = 'Oryginalna strona gazetki Lidl';
  image.src = link.href;
  image.onerror = () => { content.textContent = 'Podgląd chwilowo niedostępny.'; };
  content.replaceChildren(image);
  document.getElementById('preview').showModal();
});
