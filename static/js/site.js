const menuButton = document.querySelector("[data-menu-button]");
const mobileMenu = document.querySelector("[data-mobile-menu]");
const menuLabel = document.querySelector("[data-menu-label]");

if (menuButton && mobileMenu) {
  menuButton.addEventListener("click", () => {
    const isOpen = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isOpen));
    mobileMenu.classList.toggle("hidden", isOpen);
    if (menuLabel) {
      menuLabel.textContent = isOpen ? "Open navigation" : "Close navigation";
    }
  });
}

document.querySelectorAll(".field-has-errors .errorlist").forEach((errorList) => {
  const field = errorList.parentElement?.querySelector("input, textarea, select");
  if (!field || !errorList.id) {
    return;
  }

  field.setAttribute("aria-invalid", "true");
  field.setAttribute("aria-describedby", errorList.id);
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post") {
    return;
  }
  if (form.dataset.submitting === "true") {
    event.preventDefault();
    return;
  }

  form.dataset.submitting = "true";
  form.setAttribute("aria-busy", "true");
  form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(
    (control) => {
      control.disabled = true;
    },
  );

  const submitter = event.submitter;
  if (!(submitter instanceof HTMLButtonElement)) {
    return;
  }

  submitter.classList.add("is-loading");
  submitter.textContent = submitter.dataset.loadingLabel || "Working…";
});
