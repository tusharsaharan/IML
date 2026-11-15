/** Local demo separation, not an authentication or authorization boundary. */
export function browserScope() {
  const key = 'iml.cache.scope.v1';
  try {
    const existing = localStorage.getItem(key);
    if (existing && /^[A-Za-z0-9:_-]{1,128}$/.test(existing)) return existing;
    const generated = `browser-${crypto.randomUUID()}`;
    localStorage.setItem(key, generated);
    return generated;
  } catch { return 'browser-local'; }
}
