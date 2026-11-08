// Formatação local; funciona em formulários sem aguardar uma ida ao servidor.
export function formatMask(raw, kind) {
  const digits = String(raw ?? "").replace(/\D/g, "").slice(0, 11);
  if (kind === "cpf") {
    return digits.slice(0, 3)
      + (digits.length > 3 ? "." + digits.slice(3, 6) : "")
      + (digits.length > 6 ? "." + digits.slice(6, 9) : "")
      + (digits.length > 9 ? "-" + digits.slice(9) : "");
  }
  if (!digits) return "";
  if (digits.length <= 2) return "(" + digits;
  const prefixLength = digits.length === 11 ? 5 : 4;
  const local = digits.slice(2);
  return "(" + digits.slice(0, 2) + ") " + local.slice(0, prefixLength)
    + (local.length > prefixLength ? "-" + local.slice(prefixLength) : "");
}

export default function({ parentElement, data, setStateValue }) {
  const input = parentElement.querySelector("input");
  const label = parentElement.querySelector("label");
  label.textContent = data.label;
  input.id = data.id;
  label.htmlFor = data.id;
  input.setAttribute("aria-label", data.label);
  input.placeholder = data.kind === "cpf" ? "000.000.000-00" : "(00) 00000-0000";
  input.autocomplete = data.kind === "phone" ? "tel-national" : "off";
  const initial = formatMask(data.value, data.kind);
  if (input.value !== initial) input.value = initial;
  const commit = (raw, digitPosition) => {
    input.value = formatMask(raw, data.kind);
    let position = 0;
    let seen = 0;
    while (position < input.value.length && seen < digitPosition) {
      if (/\d/.test(input.value[position])) seen++;
      position++;
    }
    input.setSelectionRange(position, position);
    setStateValue("value", input.value);
  };
  input.oninput = () => {
    const before = input.value.slice(0, input.selectionStart);
    commit(input.value, before.replace(/\D/g, "").length);
  };
  input.onbeforeinput = (event) => {
    const cursor = input.selectionStart;
    if (event.inputType === "deleteContentBackward" && cursor === input.selectionEnd
        && cursor > 0 && /\D/.test(input.value[cursor - 1])) {
      const digitsBefore = input.value.slice(0, cursor).replace(/\D/g, "").length;
      if (digitsBefore > 0) {
        event.preventDefault();
        const digits = input.value.replace(/\D/g, "").split("");
        digits.splice(digitsBefore - 1, 1);
        commit(digits.join(""), digitsBefore - 1);
      }
    }
  };
  return () => { input.oninput = null; input.onbeforeinput = null; };
}
