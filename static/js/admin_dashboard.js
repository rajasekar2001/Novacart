
(() => {
    "use strict";

    const app = document.querySelector("#admin-app");
    if (!app) return;

    const byId = (id) => document.getElementById(id);

    const urls = {
        categories: app.dataset.categoriesUrl,
        products: app.dataset.productsUrl,
        aiProduct: app.dataset.aiProductUrl,
        aiCategory: app.dataset.aiCategoryUrl,
        quality: app.dataset.qualityUrl,
        copilot: app.dataset.copilotUrl,
        inventory: app.dataset.inventoryUrl
    };

    const state = {
        categories: [],
        products: [],
        inventory: []
    };

    function detailUrl(baseUrl, id) {
        return `${baseUrl.replace(/\/?$/, "/")}${encodeURIComponent(id)}/`;
    }

    function specificationsToText(specs) {
        if (!specs) return "";

        if (typeof specs === "string") return specs;

        if (Array.isArray(specs)) {
            return specs.map(String).join("\n");
        }

        if (typeof specs !== "object") {
            return String(specs);
        }

        return Object.entries(specs)
            .map(([key, value]) => {
                const display =
                    value && typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value ?? "");

                return `${key}: ${display}`;
            })
            .join("\n");
    }

    function csrfToken() {
        const cookie = document.cookie
            .split("; ")
            .find((item) => item.startsWith("csrftoken="));

        return cookie
            ? decodeURIComponent(cookie.split("=")[1])
            : "";
    }

    function notify(message, error = false) {
        const alert = byId("admin-alert");
        if (!alert) return;

        alert.textContent = message;
        alert.classList.toggle("error", error);
        alert.hidden = false;

        window.clearTimeout(notify.timer);

        notify.timer = window.setTimeout(() => {
            alert.hidden = true;
        }, 4500);
    }

    async function api(url, options = {}) {
        if (!url) {
            throw new Error("Dashboard API URL is missing.");
        }

        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                "X-CSRFToken": csrfToken(),
                ...(options.headers || {})
            }
        });

        const contentType =
            response.headers.get("content-type") || "";

        let data;

        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const text = await response.text();

            if (!response.ok) {
                throw new Error(
                    `Server error ${response.status}: ${response.statusText}`
                );
            }

            throw new Error(
                "The server returned an unexpected response."
            );
        }

        if (!response.ok || data.ok === false) {
            const details = data.errors
                ? Object.entries(data.errors)
                    .map(([key, value]) => {
                        const messages = Array.isArray(value)
                            ? value.join(", ")
                            : String(value);

                        return `${key}: ${messages}`;
                    })
                    .join(" | ")
                : data.message || `Request failed (${response.status}).`;

            throw new Error(details);
        }

        return data;
    }

    function showPanel(name) {
        document.querySelectorAll("[data-panel-content]")
            .forEach((panel) => {
                panel.classList.toggle(
                    "active",
                    panel.dataset.panelContent === name
                );
            });

        document.querySelectorAll(".admin-nav [data-panel]")
            .forEach((button) => {
                button.classList.toggle(
                    "active",
                    button.dataset.panel === name
                );
            });

        if (name === "categories") {
            loadCategories();
        }

        if (name === "products") {
            Promise.all([loadCategories(), loadProducts()]);
        }

        if (name === "inventory") {
            loadInventory();
        }

        if (name === "overview") {
            loadQuality();
        }
    }

    document.querySelectorAll("[data-panel]")
        .forEach((button) => {
            button.addEventListener("click", () => {
                showPanel(button.dataset.panel);
            });
        });

    document.querySelectorAll("[data-open-panel]")
        .forEach((button) => {
            button.addEventListener("click", () => {
                showPanel(button.dataset.openPanel);
            });
        });

    function cell(row, value, className = "") {
        const td = document.createElement("td");

        td.textContent = value ?? "";

        if (className) {
            td.className = className;
        }

        row.appendChild(td);
        return td;
    }

    function emptyTable(body, message, colspan) {
        body.replaceChildren();

        const row = document.createElement("tr");
        const td = cell(row, message);

        td.colSpan = colspan;
        td.style.textAlign = "center";

        body.appendChild(row);
    }

    function addActions(actionCell, item, onEdit, onDelete) {
        const actions = document.createElement("div");
        actions.className = "admin-actions";

        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "row-action";
        editButton.textContent = "Edit";

        editButton.addEventListener("click", () => {
            onEdit(item);
        });

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "row-action row-action-delete";
        deleteButton.textContent = "Delete";

        deleteButton.addEventListener("click", () => {
            onDelete(item);
        });

        actions.append(editButton, deleteButton);
        actionCell.replaceChildren(actions);
    }

    // =========================================
    // CATEGORIES
    // =========================================

    function fillCategorySelects() {
        const fields = [
            document.querySelector(
                "#category-form select[name='parent_id']"
            ),
            document.querySelector(
                "#product-form select[name='category_id']"
            ),
            byId("product-category-filter")
        ];

        fields.forEach((field) => {
            if (!field) return;

            const current = field.value;

            const firstText =
                field.name === "parent_id"
                    ? "No parent"
                    : field.id === "product-category-filter"
                        ? "All categories"
                        : "Select category";

            field.replaceChildren(new Option(firstText, ""));

            state.categories
                .filter((category) => category.active)
                .forEach((category) => {
                    field.add(
                        new Option(category.name, category.id)
                    );
                });

            field.value = current;
        });
    }

    async function loadCategories() {
        try {
            const data = await api(urls.categories);

            state.categories = data.categories || [];

            fillCategorySelects();
            renderCategories();
        } catch (error) {
            notify(error.message, true);
        }
    }

    function renderCategories() {
        const body = byId("category-rows");
        if (!body) return;

        const term = (
            byId("category-search")?.value || ""
        ).trim().toLowerCase();

        const categories = state.categories.filter((category) => {
            return String(category.name || "")
                .toLowerCase()
                .includes(term);
        });

        body.replaceChildren();

        if (!categories.length) {
            emptyTable(body, "No categories found.", 6);
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
                image.loading = "lazy";

                imageCell.appendChild(image);
            } else {
                imageCell.textContent = "—";
            }

            row.appendChild(imageCell);

            cell(row, category.name);
            cell(row, category.parent || "—");
            cell(row, category.product_count ?? 0);
            cell(row, category.active ? "Active" : "Hidden");

            const actionsCell = document.createElement("td");

            addActions(
                actionsCell,
                category,
                editCategory,
                deleteCategory
            );

            row.appendChild(actionsCell);
            body.appendChild(row);
        });
    }

    function resetCategory() {
        const form = byId("category-form");
        if (!form) return;

        form.reset();

        form.elements.category_id.value = "";
        form.elements.active.checked = true;

        byId("category-form-title").textContent = "Add category";

        byId("category-image-status").textContent =
            "Upload a JPG, PNG or WebP image.";
    }

    function editCategory(category) {
        const form = byId("category-form");

        form.elements.category_id.value = category.id;
        form.elements.name.value = category.name || "";
        form.elements.slug.value = category.slug || "";
        form.elements.parent_id.value = category.parent_id || "";
        form.elements.active.checked = Boolean(category.active);

        byId("category-form-title").textContent = "Edit category";

        byId("category-image-status").textContent =
            category.image
                ? "Current image saved. Choose a new file to replace it."
                : "No category image uploaded.";

        form.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    async function deleteCategory(category) {
        const confirmed = window.confirm(
            `Delete category "${category.name}"?\n\n` +
            "This action cannot be undone."
        );

        if (!confirmed) return;

        try {
            await api(detailUrl(urls.categories, category.id), {
                method: "DELETE"
            });

            notify(`Category "${category.name}" deleted.`);

            const form = byId("category-form");

            if (
                form.elements.category_id.value === String(category.id)
            ) {
                resetCategory();
            }

            await loadCategories();
            await loadProducts();
        } catch (error) {
            notify(
                `Could not delete category: ${error.message}`,
                true
            );
        }
    }

    byId("category-search")?.addEventListener(
        "input",
        renderCategories
    );

    byId("new-category")?.addEventListener(
        "click",
        resetCategory
    );

    byId("category-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const form = event.currentTarget;
            const id = form.elements.category_id.value;

            const payload = new FormData(form);

            payload.set(
                "active",
                form.elements.active.checked ? "true" : "false"
            );

            payload.delete("category_id");

            if (!form.elements.image.files.length) {
                payload.delete("image");
            }

            try {
                await api(
                    id
                        ? detailUrl(urls.categories, id)
                        : urls.categories,
                    {
                        method: "POST",
                        body: payload
                    }
                );

                notify(
                    id
                        ? "Category updated successfully."
                        : "Category created successfully."
                );

                resetCategory();
                await loadCategories();
            } catch (error) {
                notify(error.message, true);
            }
        }
    );

    // =========================================
    // PRODUCTS
    // =========================================

    function fillProductSelects() {
        const fields = [
            document.querySelector(
                "#variant-form select[name='product_id']"
            ),
            document.querySelector(
                "#inventory-form select[name='product_id']"
            )
        ];

        fields.forEach((field) => {
            if (!field) return;

            const current = field.value;

            field.replaceChildren(
                new Option("Select product", "")
            );

            state.products.forEach((product) => {
                field.add(
                    new Option(
                        `${product.name} (${product.category})`,
                        product.id
                    )
                );
            });

            field.value = current;
        });
    }

    async function loadProducts() {
        try {
            const data = await api(urls.products);

            state.products = data.products || [];

            fillProductSelects();
            renderProducts();
        } catch (error) {
            notify(error.message, true);
        }
    }

    function renderProducts() {
        const body = byId("product-rows");
        if (!body) return;

        const term = (
            byId("product-search")?.value || ""
        ).trim().toLowerCase();

        const categoryId =
            byId("product-category-filter")?.value || "";

        const products = state.products.filter((product) => {
            const searchText = [
                product.name,
                product.sku,
                product.brand,
                product.category
            ].join(" ").toLowerCase();

            const matchesSearch = searchText.includes(term);

            const matchesCategory =
                !categoryId ||
                String(product.category_id) === categoryId;

            return matchesSearch && matchesCategory;
        });

        body.replaceChildren();

        if (!products.length) {
            emptyTable(body, "No products found.", 5);
            return;
        }

        products.forEach((product) => {
            const row = document.createElement("tr");

            cell(row, product.name);
            cell(row, product.category);
            cell(row, `₹${product.price}`);
            cell(row, product.available_stock ?? product.stock ?? 0);

            const actionsCell = document.createElement("td");

            addActions(
                actionsCell,
                product,
                editProduct,
                deleteProduct
            );

            row.appendChild(actionsCell);
            body.appendChild(row);
        });
    }

    function resetProduct() {
        const form = byId("product-form");
        if (!form) return;

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

        [
            "name",
            "sku",
            "brand",
            "description",
            "price",
            "stock"
        ].forEach((name) => {
            form.elements[name].value = product[name] ?? "";
        });

        form.elements.category_id.value = product.category_id;

        form.elements.specifications.value =
            specificationsToText(product.specifications);

        form.elements.active.checked = Boolean(product.active);
        form.elements.featured.checked = Boolean(product.featured);

        form.elements.ingestion_source.value =
            product.ingestion_source || "manual";

        form.elements.ai_confidence.value =
            product.ai_confidence ?? "";

        form.elements.catalog_status.value =
            product.catalog_status || "published";

        byId("product-form-title").textContent = "Edit product";

        form.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    async function deleteProduct(product) {
        const confirmed = window.confirm(
            `Delete product "${product.name}"?\n\n` +
            "This action may permanently remove product data."
        );

        if (!confirmed) return;

        try {
            await api(detailUrl(urls.products, product.id), {
                method: "DELETE"
            });

            notify(`Product "${product.name}" deleted.`);

            const form = byId("product-form");

            if (
                form.elements.product_id.value === String(product.id)
            ) {
                resetProduct();
            }

            await loadProducts();
            await loadInventory();
            await loadQuality();
        } catch (error) {
            notify(
                `Could not delete product: ${error.message}`,
                true
            );
        }
    }

    byId("product-search")?.addEventListener(
        "input",
        renderProducts
    );

    byId("product-category-filter")?.addEventListener(
        "change",
        renderProducts
    );

    byId("new-product")?.addEventListener(
        "click",
        resetProduct
    );

    byId("product-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const form = event.currentTarget;
            const id = form.elements.product_id.value;

            const payload = new FormData(form);

            payload.delete("product_id");

            payload.set(
                "active",
                form.elements.active.checked ? "true" : "false"
            );

            payload.set(
                "featured",
                form.elements.featured.checked ? "true" : "false"
            );

            try {
                await api(
                    id
                        ? detailUrl(urls.products, id)
                        : urls.products,
                    {
                        method: "POST",
                        body: payload
                    }
                );

                notify(
                    id
                        ? "Product updated successfully."
                        : "Product created successfully."
                );

                resetProduct();
                await loadProducts();
            } catch (error) {
                notify(error.message, true);
            }
        }
    );

    // =========================================
    // PRODUCT VARIANTS
    // =========================================

    byId("variant-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const form = event.currentTarget;

            const payload = Object.fromEntries(
                new FormData(form)
            );

            const productId = payload.product_id;

            if (!productId) {
                notify("Please select a product.", true);
                return;
            }

            payload.active = form.elements.active.checked;

            delete payload.product_id;

            try {
                await api(
                    `${detailUrl(urls.products, productId)}variant/`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(payload)
                    }
                );

                notify("Variant saved successfully.");

                form.reset();
                form.elements.active.checked = true;

                await loadProducts();
            } catch (error) {
                notify(error.message, true);
            }
        }
    );

    // =========================================
    // INVENTORY
    // =========================================

    async function loadInventory() {
        try {
            const data = await api(urls.inventory);

            state.inventory = data.inventory || [];

            renderInventory();
        } catch (error) {
            notify(error.message, true);
        }
    }

    function renderInventory() {
        const body = byId("inventory-rows");
        if (!body) return;

        const term = (
            byId("inventory-search")?.value || ""
        ).trim().toLowerCase();

        const products = state.inventory.filter((product) => {
            return `${product.name} ${product.category}`
                .toLowerCase()
                .includes(term);
        });

        body.replaceChildren();

        if (!products.length) {
            emptyTable(body, "No inventory found.", 4);
            return;
        }

        products.forEach((product) => {
            const row = document.createElement("tr");

            cell(row, product.name);
            cell(row, product.category);
            cell(row, product.stock);
            cell(row, product.available_stock);

            body.appendChild(row);
        });
    }

    document.querySelector(
        "#inventory-form select[name='product_id']"
    )?.addEventListener("change", (event) => {
        const product = state.inventory.find(
            (item) => String(item.id) === event.target.value
        );

        const field = document.querySelector(
            "#inventory-form select[name='variant_id']"
        );

        if (!field) return;

        field.replaceChildren(
            new Option("Base product stock", "")
        );

        (product?.variants || []).forEach((variant) => {
            field.add(
                new Option(
                    `${variant.name} (${variant.stock})`,
                    variant.id
                )
            );
        });
    });

    byId("inventory-search")?.addEventListener(
        "input",
        renderInventory
    );

    byId("inventory-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const form = event.currentTarget;

            const payload = Object.fromEntries(
                new FormData(form)
            );

            try {
                const data = await api(urls.inventory, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });

                notify(
                    `Inventory updated. New stock: ` +
                    `${data.movement.stock_after}.`
                );

                form.reset();

                await loadInventory();
                await loadProducts();
            } catch (error) {
                notify(error.message, true);
            }
        }
    );

    // =========================================
    // AI CATEGORY ASSISTANT
    // =========================================

    byId("ai-category-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const result = byId("ai-category-result");

            try {
                const data = await api(urls.aiCategory, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(
                        Object.fromEntries(
                            new FormData(event.currentTarget)
                        )
                    )
                });

                result.replaceChildren();

                (data.plan.suggestions || []).forEach((item) => {
                    const div = document.createElement("div");

                    const specs = (
                        item.spec_template || []
                    ).join(", ");

                    div.textContent =
                        `${item.parent ? item.parent + " → " : ""}` +
                        `${item.name}: ${item.reason || ""}` +
                        `${specs ? " | Specs: " + specs : ""}`;

                    result.appendChild(div);
                });

                (data.plan.warnings || []).forEach((warning) => {
                    const div = document.createElement("div");

                    div.textContent = `Warning: ${warning}`;
                    result.appendChild(div);
                });

                result.hidden = false;
            } catch (error) {
                notify(error.message, true);
            }
        }
    );

    // =========================================
    // AI PRODUCT DRAFT
    // =========================================

    byId("ai-product-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const aiForm = event.currentTarget;
            const button = aiForm.querySelector(
                "button[type='submit']"
            );

            const summary = byId("ai-draft-summary");

            button.disabled = true;
            button.textContent = "Analyzing…";

            try {
                const data = await api(urls.aiProduct, {
                    method: "POST",
                    body: new FormData(aiForm)
                });

                const draft = data.draft;
                const form = byId("product-form");

                resetProduct();

                form.elements.name.value = draft.name || "";
                form.elements.brand.value = draft.brand || "";
                form.elements.sku.value = draft.sku || "";
                form.elements.description.value =
                    draft.description || "";

                form.elements.price.value = draft.price ?? "";

                form.elements.stock.value =
                    Number.isInteger(draft.stock)
                        ? draft.stock
                        : 0;

                form.elements.specifications.value =
                    specificationsToText(draft.specifications);

                if (draft.category_match) {
                    form.elements.category_id.value =
                        String(draft.category_match.id);
                }

                form.elements.ingestion_source.value = "ai";

                form.elements.ai_confidence.value =
                    draft.confidence ?? "";

                form.elements.ai_missing_fields.value =
                    JSON.stringify(draft.missing_fields || []);

                form.elements.ai_warnings.value =
                    JSON.stringify(draft.warnings || []);

                form.elements.catalog_status.value = "draft";
                form.elements.active.checked = false;

                byId("product-form-title").textContent =
                    "Review AI product draft";

                const missing = (
                    draft.missing_fields || []
                ).join(", ") || "None reported";

                const warnings = (
                    draft.warnings || []
                ).join(" • ") || "None";

                const duplicates = (
                    draft.duplicate_candidates || []
                ).map((item) => {
                    return item.sku
                        ? `${item.name} (${item.sku})`
                        : item.name;
                }).join(", ") || "None found";

                const confidence =
                    Math.round((draft.confidence || 0) * 100);

                summary.textContent =
                    `Confidence: ${confidence}% | ` +
                    `Missing: ${missing} | ` +
                    `Warnings: ${warnings} | ` +
                    `Possible duplicates: ${duplicates}`;

                summary.hidden = false;

                notify(
                    "AI draft generated. Review before publishing."
                );

                form.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            } catch (error) {
                notify(error.message, true);
            } finally {
                button.disabled = false;
                button.textContent = "Analyze with AI";
            }
        }
    );

    // =========================================
    // AI QUALITY CHECK
    // =========================================

    async function loadQuality() {
        const summary = byId("quality-summary");
        const list = byId("quality-products");

        if (!summary || !urls.quality) return;

        try {
            const data = await api(urls.quality);
            const q = data.summary;

            summary.textContent =
                `${q.needs_review} of ${q.total} products need review · ` +
                `${q.missing_images} missing images · ` +
                `${q.missing_specs} missing specs · ` +
                `${q.low_stock} low stock`;

            list.replaceChildren();

            (data.products || []).slice(0, 6).forEach((product) => {
                const div = document.createElement("div");

                div.textContent =
                    `${product.name} — ${product.score}% · ` +
                    `${(product.issues || []).join(", ")}`;

                list.appendChild(div);
            });
        } catch (error) {
            summary.textContent = error.message;
        }
    }

    byId("refresh-quality")?.addEventListener(
        "click",
        loadQuality
    );

    // =========================================
    // AI COPILOT
    // =========================================

    byId("ai-copilot-form")?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const answer = byId("ai-copilot-answer");

            try {
                const data = await api(urls.copilot, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(
                        Object.fromEntries(
                            new FormData(event.currentTarget)
                        )
                    )
                });

                answer.textContent = data.answer || "";
                answer.hidden = false;
            } catch (error) {
                notify(error.message, true);
            }
        }
    );

    // =========================================
    // INITIAL LOAD
    // =========================================

    Promise.all([
        loadCategories(),
        loadProducts()
    ]);

    loadQuality();

})();
