const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const forms = document.querySelectorAll(".ocr-form");
const output = document.querySelector("#output");
const links = document.querySelector("#links");
const copyButton = document.querySelector("#copy-result");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    panels.forEach((panel) => panel.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`#panel-${tab.dataset.panel}`).classList.add("active");
  });
});

forms.forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector('button[type="submit"]');
    const formData = new FormData(form);

    submit.disabled = true;
    output.classList.remove("error");
    output.textContent = "Processing...";
    links.innerHTML = "";

    try {
      const response = await fetch(form.dataset.endpoint, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      output.textContent = JSON.stringify(data, null, 2);
      output.classList.toggle("error", !response.ok);
      renderLinks(data);
    } catch (error) {
      output.classList.add("error");
      output.textContent = JSON.stringify({ message: error.message }, null, 2);
    } finally {
      submit.disabled = false;
    }
  });
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(output.textContent);
  copyButton.textContent = "Copied";
  setTimeout(() => {
    copyButton.textContent = "Copy JSON";
  }, 1200);
});

function renderLinks(data) {
  const urlFields = ["url", "file_path", "front_file_path", "back_file_path"];
  urlFields.forEach((field) => {
    if (typeof data[field] === "string" && data[field].startsWith("http")) {
      const anchor = document.createElement("a");
      anchor.href = data[field];
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
      anchor.textContent = field;
      links.appendChild(anchor);
    }
  });
}
