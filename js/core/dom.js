export function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

export function showElement(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = false;
}
