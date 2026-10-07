(() => {
  const app = document.querySelector("#admin-app");
  if (!app) return;

  const urls = {
    categories: app.dataset.categoriesUrl,
    products: app.dataset.productsUrl,
    aiProduct: app.dataset.aiProductUrl,
    inventory: app.dataset.inventoryUrl,
    aiCategory: app.dataset.aiCategoryUrl,
    quality: app.dataset.qualityUrl,
    copilot: app.dataset.copilotUrl,
  };
  const state = {categories: [], products: []};
  const byId = (id) => document.getElementById(id);

  function csrfToken() {
    return document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=")[1] || "";
  }

  function notify(message, error = false) {
    const alert = byId("admin-alert");
    alert.textContent = message;
    alert.classList.toggle("error", error);
    alert.hidden = false;
    window.clearTimeout(notify.timer);
    notify.timer = window.setTimeout(() => { alert.hidden = true; }, 4500);
  }

  async function api(url, options = {}) {
    if (!url) {
      throw new Error("Dashboard API URL is missing. Refresh the page and verify the dashboard data-* URL attributes.");
    }
    const response = await fetch(url, {
      ...options,
      headers: {"X-CSRFToken": csrfToken(), ...(options.headers || {})},
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      const details = data.errors
        ? Object.entries(data.errors).map(([key, value]) => `${key}: ${[].concat(value).join(", ")}`).join(" | ")
        : "Request failed.";
      throw new Error(details);
    }
    return data;
  }

  function showPanel(name) {
    document.querySelectorAll("[data-panel-content]").forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.panelContent === name);
    });
    document.querySelectorAll(".admin-nav [data-panel]").forEach((button) => {
      button.classList.toggle("active", button.dataset.panel === name);
    });
    if (name === "categories") loadCategories();
    if (name === "products") Promise.all([loadCategories(), loadProducts()]);
    if (name === "inventory") loadInventory();
    if (name === "overview") loadQuality();
  }

  document.querySelectorAll("[data-panel]").forEach((button) => {
    button.addEventListener("click", () => showPanel(button.dataset.panel));
  });
  document.querySelectorAll("[data-open-panel]").forEach((button) => {
    button.addEventListener("click", () => showPanel(button.dataset.openPanel));
  });

  function cell(row, value, className = "") {
    const element = document.createElement("td");
    element.textContent = value ?? "";
    if (className) element.className = className;
    row.appendChild(element);
    return element;
  }

  function actionCell(row, label, callback) {
    const column = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "row-action";
    button.textContent = label;
    button.addEventListener("click", callback);
    column.appendChild(button);
    row.appendChild(column);
  }

  function fillCategorySelects() {
    const fields = [
      document.querySelector("#category-form select[name='parent_id']"),
      document.querySelector("#product-form select[name='category_id']"),
      byId("product-category-filter"),
    ];
    fields.forEach((field) => {
      if (!field) return;
      const current = field.value;
      const firstText = field.name === "parent_id" ? "No parent" : field.id === "product-category-filter" ? "All categories" : "Select category";
      field.replaceChildren(new Option(firstText, ""));
      state.categories.filter((item) => item.active).forEach((category) => {
        field.add(new Option(category.name, category.id));
      });
      field.value = current;
    });
  }

  async function loadCategories() {
    try {
      const data = await api(urls.categories);
      state.categories = data.categories;
      fillCategorySelects();
      renderCategories();
    } catch (error) { notify(error.message, true); }
  }

  function renderCategories() {
    const body = byId("category-rows");
    const term = byId("category-search").value.trim().toLowerCase();
    body.replaceChildren();
    const categories = state.categories.filter((item) => item.name.toLowerCase().includes(term));
    if (!categories.length) {
      const row = document.createElement("tr");
      cell(row, "No categories found.").colSpan = 6;
      body.appendChild(row);
      return;
    }
    categories.forEach((category) => {
      const row = document.createElement("tr");
      const imageCell = document.createElement("td");
      if (category.image) {
        const image = document.createElement("img");
        image.src = category.image;
        image.alt = category.name;
        image.className = "admin-thumb";
        imageCell.appendChild(image);
      } else {
        imageCell.textContent = "—";
      }
      row.appendChild(imageCell);
      cell(row, category.name);
      cell(row, category.parent || "-");
      cell(row, category.product_count);
      cell(row, category.active ? "Active" : "Hidden");
      actionCell(row, "Edit", () => editCategory(category));
      body.appendChild(row);
    });
  }

  function resetCategory() {
    const form = byId("category-form");
    form.reset();
    form.elements.category_id.value = "";
    form.elements.active.checked = true;
    byId("category-image-status").textContent = "Upload a JPG, PNG or WebP image.";
    byId("category-form-title").textContent = "Add category";
  }

  function editCategory(category) {
    const form = byId("category-form");
    form.elements.category_id.value = category.id;
    form.elements.name.value = category.name;
    form.elements.slug.value = category.slug;
    form.elements.parent_id.value = category.parent_id || "";
    form.elements.active.checked = category.active;
    byId("category-image-status").textContent = category.image
      ? "Current image is saved. Choose another file to replace it."
      : "No category image uploaded.";
    byId("category-form-title").textContent = "Edit category";
    form.scrollIntoView({behavior: "smooth", block: "start"});
  }

  byId("ai-category-form")?.addEventListener("submit", async (event) => {
    event.preventDefault(); const result = byId("ai-category-result");
    try {
      const data = await api(urls.aiCategory, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))) });
      result.replaceChildren();
      (data.plan.suggestions || []).forEach((item) => { const div=document.createElement("div"); const specs=(item.spec_template||[]).join(", "); div.textContent=`${item.parent ? item.parent + " → " : ""}${item.name}: ${item.reason || ""}${specs ? " | Specs: " + specs : ""}`; result.appendChild(div); });
      (data.plan.warnings||[]).forEach(w=>{const div=document.createElement("div"); div.textContent=`Warning: ${w}`; result.appendChild(div);}); result.hidden=false;
    } catch(error){ notify(error.message,true); }
  });

  async function loadQuality(){
    const summary=byId("quality-summary"), list=byId("quality-products"); if(!summary || !urls.quality) return;
    try { const data=await api(urls.quality); const q=data.summary; summary.textContent=`${q.needs_review} of ${q.total} products need review · ${q.missing_images} missing images · ${q.missing_specs} missing specs · ${q.low_stock} low stock`; list.replaceChildren(); data.products.slice(0,6).forEach(p=>{const div=document.createElement("div"); div.textContent=`${p.name} — ${p.score}% · ${p.issues.join(", ")}`; list.appendChild(div);}); } catch(error){ summary.textContent=error.message; }
  }
  byId("refresh-quality")?.addEventListener("click", loadQuality);
  byId("ai-copilot-form")?.addEventListener("submit", async(event)=>{ event.preventDefault(); const answer=byId("ai-copilot-answer"); try { const data=await api(urls.copilot,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(new FormData(event.currentTarget)))}); answer.textContent=data.answer; answer.hidden=false; } catch(error){notify(error.message,true);} });
  loadQuality();

  byId("category-search").addEventListener("input", renderCategories);
  byId("new-category").addEventListener("click", resetCategory);
  byId("category-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const id = form.elements.category_id.value;
    const payload = new FormData(form);
    payload.set("active", form.elements.active.checked ? "true" : "false");
    payload.delete("category_id");
    if (!form.elements.image.files.length) payload.delete("image");
    try {
      await api(id ? `${urls.categories}${id}/` : urls.categories, {
        method: "POST", body: payload,
      });
      notify(id ? "Category updated." : "Category created.");
      resetCategory();
      await loadCategories();
    } catch (error) { notify(error.message, true); }
  });

  function fillProductSelects() {
    const fields = [
      document.querySelector("#variant-form select[name='product_id']"),
      document.querySelector("#inventory-form select[name='product_id']"),
    ];
    fields.forEach((field) => {
      const current = field.value;
      field.replaceChildren(new Option("Select product", ""));
      state.products.forEach((product) => field.add(new Option(`${product.name} (${product.category})`, product.id)));
      field.value = current;
    });
  }

  async function loadProducts() {
    try {
      const data = await api(urls.products);
      state.products = data.products;
      fillProductSelects();
      renderProducts();
    } catch (error) { notify(error.message, true); }
  }

  function renderProducts() {
    const body = byId("product-rows");
    const term = byId("product-search").value.trim().toLowerCase();
    const categoryId = byId("product-category-filter").value;
    body.replaceChildren();
    const products = state.products.filter((item) => {
      const matchesTerm = [item.name, item.sku, item.brand, item.category].join(" ").toLowerCase().includes(term);
      return matchesTerm && (!categoryId || String(item.category_id) === categoryId);
    });
    if (!products.length) {
      const row = document.createElement("tr");
      cell(row, "No products found.").colSpan = 5;
      body.appendChild(row);
      return;
    }
    products.forEach((product) => {
      const row = document.createElement("tr");
      cell(row, product.name);
      cell(row, product.category);
      cell(row, `₹${product.price}`);
      cell(row, product.available_stock);
      actionCell(row, "Edit", () => editProduct(product));
      body.appendChild(row);
    });
  }

  function resetProduct() {
    const form = byId("product-form");
    form.reset();
    form.elements.product_id.value = "";
    form.elements.active.checked = true;
    form.elements.ingestion_source.value = "manual";
    form.elements.ai_confidence.value = "";
    form.elements.ai_missing_fields.value = "[]";
    form.elements.ai_warnings.value = "[]";
    form.elements.catalog_status.value = "published";
    byId("product-form-title").textContent = "Add product";
  }

  function editProduct(product) {
    const form = byId("product-form");
    form.elements.product_id.value = product.id;
    ["name", "sku", "brand", "description", "price", "stock"].forEach((name) => {
      form.elements[name].value = product[name] ?? "";
    });
    form.elements.category_id.value = product.category_id;
    form.elements.specifications.value = JSON.stringify(product.specifications || {}, null, 2);
    form.elements.active.checked = product.active;
    form.elements.featured.checked = product.featured;
    form.elements.ingestion_source.value = product.ingestion_source || "manual";
    form.elements.ai_confidence.value = product.ai_confidence ?? "";
    form.elements.catalog_status.value = product.catalog_status || "published";
    byId("product-form-title").textContent = "Edit product";
    form.scrollIntoView({behavior: "smooth", block: "start"});
  }

  byId("ai-product-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const aiForm = event.currentTarget;
    const button = aiForm.querySelector("button[type='submit']");
    const summary = byId("ai-draft-summary");
    button.disabled = true;
    button.textContent = "Analyzing…";
    try {
      const data = await api(urls.aiProduct, {method: "POST", body: new FormData(aiForm)});
      const draft = data.draft;
      const form = byId("product-form");
      resetProduct();
      form.elements.name.value = draft.name || "";
      form.elements.brand.value = draft.brand || "";
      form.elements.sku.value = draft.sku || "";
      form.elements.description.value = draft.description || "";
      form.elements.price.value = draft.price || "";
      form.elements.stock.value = Number.isInteger(draft.stock) ? draft.stock : 0;
      form.elements.specifications.value = JSON.stringify(draft.specifications || {}, null, 2);
      if (draft.category_match) form.elements.category_id.value = String(draft.category_match.id);
      form.elements.ingestion_source.value = "ai";
      form.elements.ai_confidence.value = draft.confidence ?? "";
      form.elements.ai_missing_fields.value = JSON.stringify(draft.missing_fields || []);
      form.elements.ai_warnings.value = JSON.stringify(draft.warnings || []);
      form.elements.catalog_status.value = "draft";
      form.elements.active.checked = false;
      byId("product-form-title").textContent = "Review AI product draft";

      const missing = (draft.missing_fields || []).join(", ") || "None reported";
      const warnings = (draft.warnings || []).join(" • ") || "None";
      const duplicates = (draft.duplicate_candidates || []).map(x => `${x.name}${x.sku ? ` (${x.sku})` : ""}`).join(", ") || "None found";
      summary.textContent = `Confidence: ${Math.round((draft.confidence || 0) * 100)}% | Missing: ${missing} | Warnings: ${warnings} | Possible duplicates: ${duplicates}`;
      summary.hidden = false;
      notify("AI draft generated. Review every field before publishing.");
      form.scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
      notify(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = "Analyze with AI";
    }
  });

  byId("product-search").addEventListener("input", renderProducts);
  byId("product-category-filter").addEventListener("change", renderProducts);
  byId("new-product").addEventListener("click", resetProduct);
  byId("product-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const id = form.elements.product_id.value;
    const payload = new FormData(form);
    payload.delete("product_id");
    payload.set("active", form.elements.active.checked ? "true" : "false");
    payload.set("featured", form.elements.featured.checked ? "true" : "false");
    try {
      await api(id ? `${urls.products}${id}/` : urls.products, {method: "POST", body: payload});
      notify(id ? "Product updated." : "Product created under its selected category.");
      resetProduct();
      await loadProducts();
    } catch (error) { notify(error.message, true); }
  });

  byId("variant-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form));
    const productId = payload.product_id;
    payload.active = form.elements.active.checked;
    delete payload.product_id;
    try {
      await api(`${urls.products}${productId}/variant/`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
      });
      notify("Variant saved.");
      form.reset();
      form.elements.active.checked = true;
      await loadProducts();
    } catch (error) { notify(error.message, true); }
  });

  async function loadInventory() {
    try {
      const data = await api(urls.inventory);
      state.products = data.inventory;
      fillProductSelects();
      renderInventory();
    } catch (error) { notify(error.message, true); }
  }

  function renderInventory() {
    const body = byId("inventory-rows");
    const term = byId("inventory-search").value.trim().toLowerCase();
    body.replaceChildren();
    state.products.filter((product) => `${product.name} ${product.category}`.toLowerCase().includes(term)).forEach((product) => {
      const row = document.createElement("tr");
      cell(row, product.name);
      cell(row, product.category);
      cell(row, product.stock);
      cell(row, product.available_stock);
      body.appendChild(row);
    });
  }

  document.querySelector("#inventory-form select[name='product_id']").addEventListener("change", (event) => {
    const product = state.products.find((item) => String(item.id) === event.target.value);
    const field = document.querySelector("#inventory-form select[name='variant_id']");
    field.replaceChildren(new Option("Base product stock", ""));
    (product?.variants || []).forEach((variant) => field.add(new Option(`${variant.name} (${variant.stock})`, variant.id)));
  });
  byId("inventory-search").addEventListener("input", renderInventory);
  byId("inventory-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form));
    try {
      const data = await api(urls.inventory, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
      });
      notify(`Inventory updated. New stock: ${data.movement.stock_after}.`);
      form.reset();
      await loadInventory();
    } catch (error) { notify(error.message, true); }
  });

  Promise.all([loadCategories(), loadProducts()]);
})();
