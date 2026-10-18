document.addEventListener("DOMContentLoaded", () => {
  // Add a brief confirmation before leaving forms that create records.
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Prevent accidental double-clicks on submit buttons.
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"]');
      if (button && !button.dataset.noDisable) {
        button.dataset.originalText = button.textContent;
        button.disabled = true;
        button.classList.add("is-submitting");
        window.setTimeout(() => {
          button.disabled = false;
          button.classList.remove("is-submitting");
        }, 2500);
      }
    });
  });
});
