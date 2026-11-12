// O PDF chega pronto: este componente somente inicia a transferência ao navegador.
// A mesma resposta não pode disparar um segundo download em uma remontagem.
const delivered = new Set();

export default function({ parentElement, data }) {
  if (!data.token || !data.content || delivered.has(data.token)) return;
  const storageKey = `oficina-download-${data.token}`;
  try {
    if (sessionStorage.getItem(storageKey)) return;
  } catch { /* O controle em memória cobre navegadores sem sessionStorage. */ }

  const bytes = Uint8Array.from(atob(data.content), char => char.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = data.filename;
  link.hidden = true;
  parentElement.appendChild(link);
  link.click();
  link.remove();
  delivered.add(data.token);
  try { sessionStorage.setItem(storageKey, "1"); } catch { /* opcional */ }
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
