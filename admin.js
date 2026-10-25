let csrfToken = "";
let adminUsername = "";
let currency = "USD";
let locale = "en-US";
let products = [];
let orders = [];
let categories = [];
let outlets = [];
let customers = [];
let settings = { low_stock_threshold: 5 };
let editingProductId = null;
let editingOutletId = null;
let selectedImageFile = null;
let currentImagePath = null;
let previewObjectUrl = null;
let selectedStoreLogoFile = null;
let currentStoreLogoPath = null;
let storeLogoPreviewObjectUrl = null;
let selectedStoreCoverFile = null;
let currentStoreCoverPath = null;
let storeCoverPreviewObjectUrl = null;
let selectedOwnerImageFile = null;
let currentOwnerImagePath = null;
let ownerImagePreviewObjectUrl = null;
let toastTimer;

const loginPanel = document.querySelector("#login-panel");
const dashboard = document.querySelector("#dashboard");
const loginForm = document.querySelector("#login-form");
const dashboardError = document.querySelector("#dashboard-error");
const productDialog = document.querySelector("#product-dialog");
const productForm = document.querySelector("#product-form");
const formatter = () => new Intl.NumberFormat(locale, { style: "currency", currency });

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function showError(element, message) {
  element.textContent = message;
  element.hidden = false;
}

function clearError(element) {
  element.textContent = "";
  element.hidden = true;
}

function notify(message) {
  const toast = document.querySelector("#admin-toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2400);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (options.method && !["GET", "HEAD"].includes(options.method.toUpperCase()) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  const result = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) showLogin();
    const detail = result?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : "The request could not be completed.";
    throw new Error(message);
  }
  return result;
}

function showLogin() {
  csrfToken = "";
  loginPanel.hidden = false;
  dashboard.hidden = true;
  document.querySelector("#logout-button").hidden = true;
}

function showDashboard(username) {
  adminUsername = username;
  document.querySelector("#admin-username").textContent = username;
  loginPanel.hidden = true;
  dashboard.hidden = false;
  document.querySelector("#logout-button").hidden = false;
}

async function loadDashboardData() {
  clearError(dashboardError);
  try {
    const [config, summary, productRows, orderRows, categoryRows, outletRows, customerRows, storeSettings] = await Promise.all([
      api("/api/config"),
      api("/api/admin/summary"),
      api("/api/admin/products"),
      api("/api/admin/orders"),
      api("/api/admin/categories"),
      api("/api/admin/outlets"),
      api("/api/admin/customers"),
      api("/api/admin/settings")
    ]);
    currency = config.currency;
    locale = config.locale;
    document.title = `Store admin | ${config.business_name}`;
    document.querySelector(".admin-brand > span:last-child").textContent = config.business_name.toUpperCase();
    renderAdminLogo(config.logo_url);
    products = productRows;
    orders = orderRows;
    categories = categoryRows;
    outlets = outletRows;
    customers = customerRows;
    settings = storeSettings;
    document.querySelector("#stat-products").textContent = summary.total_products;
    document.querySelector("#stat-new-orders").textContent = summary.new_orders;
    document.querySelector("#stat-orders").textContent = summary.total_orders;
    document.querySelector("#stat-low-stock").textContent = summary.low_stock;
    document.querySelector("#low-stock-caption").textContent = `At or below ${settings.low_stock_threshold} in stock`;
    renderRecentOrders();
    renderProducts();
    renderOrders();
    renderCustomers();
    renderCategories();
    renderOutlets();
    fillSettingsForm();
  } catch (error) {
    showError(dashboardError, error instanceof Error ? error.message : "Could not load store data.");
  }
}

function renderRecentOrders() {
  const container = document.querySelector("#recent-orders");
  const latest = orders.slice(0, 4);
  container.innerHTML = latest.length ? latest.map((order) => `
    <article class="recent-order">
      <div><strong>${escapeHTML(order.order_number)}</strong><span>${escapeHTML(order.customer_name)} &middot; ${escapeHTML(formatDate(order.created_at))}</span></div>
      <span class="status-pill status-${escapeHTML(order.status)}">${escapeHTML(order.status)}</span>
      <span class="recent-total">${formatter().format(order.subtotal_cents / 100)}</span>
    </article>`).join("") : '<p class="table-empty">No order requests yet.</p>';
}

function getVisibleProducts() {
  const query = document.querySelector("#product-search").value.trim().toLowerCase();
  const status = document.querySelector("#product-status-filter").value;
  const lowStockOnly = document.querySelector("#low-stock-only").checked;
  return products.filter((product) => {
    const matchesStatus = status === "all" || (status === "active" ? product.active : !product.active);
    const matchesQuery = `${product.name} ${product.category}`.toLowerCase().includes(query);
    const matchesStock = !lowStockOnly || (product.active && product.stock_quantity <= settings.low_stock_threshold);
    return matchesStatus && matchesQuery && matchesStock;
  });
}

function renderProducts() {
  const rows = getVisibleProducts();
  document.querySelector("#products-empty").hidden = rows.length > 0;
  document.querySelector("#products-table").innerHTML = rows.map((product) => `
    <tr>
      <td class="table-product"><div class="admin-product-row"><span class="admin-product-thumb">${product.image_url ? `<img src="${escapeHTML(product.image_url)}" alt="" />` : "AM"}</span><span><strong>${escapeHTML(product.name)}</strong><small>${escapeHTML(product.note || "No color note")}</small></span></div></td>
      <td>${escapeHTML(product.category)}</td>
      <td>${formatter().format(product.price)}</td>
      <td><div class="inventory-control ${product.stock_quantity <= settings.low_stock_threshold && product.active ? "stock-low" : ""}">${product.active ? `<button type="button" data-stock-change="-1" data-stock-product="${escapeHTML(product.id)}" aria-label="Decrease ${escapeHTML(product.name)} stock">&#8722;</button>` : ""}<strong>${product.stock_quantity}</strong>${product.active ? `<button type="button" data-stock-change="1" data-stock-product="${escapeHTML(product.id)}" aria-label="Increase ${escapeHTML(product.name)} stock">+</button>` : ""}</div>${product.active && product.stock_quantity <= settings.low_stock_threshold ? '<small class="low-stock-label">Low stock</small>' : ""}</td>
      <td><span class="status-pill ${product.active ? "status-fulfilled" : "status-archived"}">${product.active ? "Active" : "Archived"}</span></td>
      <td><button class="table-action" type="button" data-edit-product="${escapeHTML(product.id)}">Edit</button> ${product.active ? `<button class="table-action danger" type="button" data-archive-product="${escapeHTML(product.id)}">Archive</button>` : ""}</td>
    </tr>`).join("");
}

function getVisibleOrders() {
  const status = document.querySelector("#order-status-filter").value;
  return status === "all" ? orders : orders.filter((order) => order.status === status);
}

function allowedNextStatuses(status) {
  if (status === "new") return ["confirmed", "cancelled"];
  if (status === "confirmed") return ["fulfilled", "cancelled"];
  return [];
}

function renderOrders() {
  const rows = getVisibleOrders();
  document.querySelector("#orders-empty").hidden = rows.length > 0;
  document.querySelector("#orders-table").innerHTML = rows.map((order) => {
    const nextStatuses = allowedNextStatuses(order.status);
    const statusControl = nextStatuses.length ? `
      <select class="order-select" data-order-status="${escapeHTML(order.id)}" aria-label="Update ${escapeHTML(order.order_number)} status">
        <option value="">Update</option>
        ${nextStatuses.map((next) => `<option value="${next}">${escapeHTML(next)}</option>`).join("")}
      </select>` : '<span class="muted-cell">No further action</span>';
    const itemSummary = order.items.map((item) => `${item.quantity} x ${item.product_name}`).join(", ");
    return `
      <tr>
        <td class="table-product"><strong>${escapeHTML(order.order_number)}</strong><small>${escapeHTML(formatDate(order.created_at))}</small></td>
        <td class="order-customer"><strong>${escapeHTML(order.customer_name)}</strong><small>${escapeHTML(order.email)} &middot; ${escapeHTML(order.phone)}</small></td>
        <td class="order-items-summary" title="${escapeHTML(itemSummary)}">${escapeHTML(itemSummary)}</td>
        <td>${formatter().format(order.subtotal_cents / 100)}</td>
        <td><span class="status-pill status-${escapeHTML(order.status)}">${escapeHTML(order.status)}</span></td>
        <td>${statusControl}</td>
        <td><button class="table-action" type="button" data-order-detail="${escapeHTML(order.id)}">Details</button></td>
      </tr>`;
  }).join("");
}

function renderCustomers() {
  const query = document.querySelector("#customer-search").value.trim().toLowerCase();
  const rows = customers.filter((customer) =>
    `${customer.customer_name} ${customer.email} ${customer.phone}`.toLowerCase().includes(query)
  );
  document.querySelector("#customers-empty").hidden = rows.length > 0;
  document.querySelector("#customers-table").innerHTML = rows.map((customer) => `
    <tr>
      <td class="order-customer"><strong>${escapeHTML(customer.customer_name)}</strong><small>${escapeHTML(customer.email)} &middot; ${escapeHTML(customer.phone)}</small></td>
      <td>${customer.order_count}</td>
      <td>${formatter().format(customer.total_order_value_cents / 100)}</td>
      <td>${escapeHTML(formatDate(customer.last_order_at))}</td>
      <td><details class="customer-history"><summary>Order history</summary><div>${customer.orders.map((order) => `<button type="button" class="history-order" data-customer-order-detail="${escapeHTML(order.id)}"><strong>${escapeHTML(order.order_number)}</strong><span>${escapeHTML(order.status)} &middot; ${formatter().format(order.subtotal_cents / 100)}</span></button>`).join("")}</div></details></td>
    </tr>`).join("");
}

function renderCategories() {
  const activeCategories = categories.filter((category) => category.active);
  document.querySelector("#categories-empty").hidden = activeCategories.length > 0;
  document.querySelector("#category-list").innerHTML = activeCategories.map((category) => `
    <form class="category-row" data-rename-category="${category.id}">
      <input name="name" value="${escapeHTML(category.name)}" minlength="2" maxlength="50" required aria-label="Category name" />
      <input name="name_ar" value="${escapeHTML(category.name_ar || "")}" maxlength="50" dir="rtl" aria-label="Arabic category name" />
      <button class="table-action" type="submit">Save name</button>
      <button class="table-action danger" type="button" data-archive-category="${category.id}">Remove</button>
    </form>`).join("");
}

function renderOutlets() {
  const list = document.querySelector("#outlet-admin-list");
  const active = outlets.filter((outlet) => outlet.active);
  document.querySelector("#outlets-admin-empty").hidden = active.length > 0;
  list.innerHTML = active.map((outlet) => `
    <article class="outlet-admin-item">
      <div><strong>${escapeHTML(outlet.name_en)}</strong><span dir="rtl">${escapeHTML(outlet.name_ar)}</span></div>
      <p>${escapeHTML(outlet.address_en)}</p><p dir="rtl">${escapeHTML(outlet.address_ar)}</p>
      <small>${escapeHTML(outlet.phone)}${outlet.hours_en ? ` · ${escapeHTML(outlet.hours_en)}` : ""}</small>
      ${outlet.hours_ar ? `<small dir="rtl">${escapeHTML(outlet.hours_ar)}</small>` : ""}
      <div class="outlet-item-actions"><button class="table-action" type="button" data-edit-outlet="${outlet.id}">Edit</button><button class="table-action danger" type="button" data-archive-outlet="${outlet.id}">Archive</button></div>
    </article>`).join("");
}

function fillOutletForm(outlet = null) {
  const form = document.querySelector("#outlet-form");
  editingOutletId = outlet?.id || null;
  form.elements.id.value = editingOutletId || "";
  for (const key of ["name_en", "name_ar", "address_en", "address_ar", "phone", "hours_en", "hours_ar"]) {
    form.elements[key].value = outlet?.[key] || "";
  }
  document.querySelector("#save-outlet").innerHTML = editingOutletId ? 'Save outlet <span aria-hidden="true">&#8594;</span>' : 'Add outlet <span aria-hidden="true">&#8594;</span>';
  clearError(document.querySelector("#outlet-error"));
}

function fillSettingsForm() {
  const form = document.querySelector("#settings-form");
  if (!form || !settings.business_name) return;
  for (const key of ["business_name", "business_name_ar", "about_en", "about_ar", "about_eyebrow_en", "about_title_en", "about_lead_en", "about_story_eyebrow_en", "about_story_heading_en", "about_story_en", "about_story_secondary_en", "owner_name", "owner_eyebrow_en", "owner_role", "owner_bio", "about_primary_color", "about_background_color", "about_surface_color", "about_accent_color", "about_values_eyebrow_en", "about_contact_eyebrow_en", "about_contact_title_en", "about_contact_text_en", "currency", "locale", "contact_email", "contact_phone", "business_address", "low_stock_threshold"]) {
    form.elements[key].value = settings[key] ?? "";
  }
  currentStoreLogoPath = settings.logo_path || null;
  selectedStoreLogoFile = null;
  document.querySelector("#store-logo-file").value = "";
  if (storeLogoPreviewObjectUrl) URL.revokeObjectURL(storeLogoPreviewObjectUrl);
  storeLogoPreviewObjectUrl = null;
  renderStoreLogoPreview(settings.logo_url || null);
  currentStoreCoverPath = settings.cover_path || null;
  selectedStoreCoverFile = null;
  document.querySelector("#store-cover-file").value = "";
  if (storeCoverPreviewObjectUrl) URL.revokeObjectURL(storeCoverPreviewObjectUrl);
  storeCoverPreviewObjectUrl = null;
  renderStoreCoverPreview(settings.cover_url || null);
  form.elements.cover_fit.value = settings.cover_fit || "cover";
  currentOwnerImagePath = settings.owner_image_path || null;
  selectedOwnerImageFile = null;
  document.querySelector("#owner-image-file").value = "";
  if (ownerImagePreviewObjectUrl) URL.revokeObjectURL(ownerImagePreviewObjectUrl);
  ownerImagePreviewObjectUrl = null;
  renderOwnerImagePreview(settings.owner_image_url || null);
}

function renderStoreLogoPreview(source) {
  const image = document.querySelector("#store-logo-preview");
  const placeholder = document.querySelector("#store-logo-placeholder");
  image.hidden = !source;
  placeholder.hidden = Boolean(source);
  if (source) image.src = source;
  else image.removeAttribute("src");
}

function renderStoreCoverPreview(source) {
  const image = document.querySelector("#store-cover-preview");
  const placeholder = document.querySelector("#store-cover-placeholder");
  image.hidden = !source;
  placeholder.hidden = Boolean(source);
  if (source) image.src = source;
  else image.removeAttribute("src");
}

function renderOwnerImagePreview(source) {
  const image = document.querySelector("#owner-image-preview");
  const placeholder = document.querySelector("#owner-image-placeholder");
  image.hidden = !source;
  placeholder.hidden = Boolean(source);
  if (source) image.src = source;
  else image.removeAttribute("src");
}

function renderAdminLogo(source) {
  const mark = document.querySelector("#admin-brand-mark");
  const image = document.querySelector("#admin-brand-image");
  image.hidden = !source;
  mark.classList.toggle("has-logo", Boolean(source));
  if (source) image.src = source;
  else image.removeAttribute("src");
}

async function openOrderDetails(orderId) {
  try {
    const order = await api(`/api/admin/orders/${encodeURIComponent(orderId)}`);
    document.querySelector("#order-dialog-title").textContent = order.order_number;
    document.querySelector("#order-detail-content").innerHTML = `
      <div class="order-detail-contact">
        <div><span>Customer</span><strong>${escapeHTML(order.customer_name)}</strong></div>
        <div><span>Email</span><strong>${escapeHTML(order.email)}</strong></div>
        <div><span>Phone</span><strong>${escapeHTML(order.phone)}</strong></div>
        <div><span>Delivery address</span><strong>${escapeHTML(order.delivery_address)}</strong></div>
        <div><span>Requested</span><strong>${escapeHTML(formatDate(order.created_at))}</strong></div>
        <div><span>Status</span><strong class="status-pill status-${escapeHTML(order.status)}">${escapeHTML(order.status)}</strong></div>
      </div>
      <div class="order-detail-items"><h3>Items</h3>${order.items.map((item) => `<div><span>${item.quantity} x ${escapeHTML(item.product_name)}</span><strong>${formatter().format(item.unit_price_cents * item.quantity / 100)}</strong></div>`).join("")}</div>
      <div class="order-detail-total"><span>Subtotal</span><strong>${formatter().format(order.subtotal_cents / 100)}</strong></div>
      <p class="order-detail-note">Payment is not collected online. Contact the customer to confirm payment and delivery arrangements.</p>`;
    document.querySelector("#order-dialog").showModal();
  } catch (error) {
    showError(dashboardError, error instanceof Error ? error.message : "Could not load order details.");
  }
}

function formatDate(value) {
  const parsed = new Date(`${value.replace(" ", "T")}Z`);
  return Number.isNaN(parsed.valueOf()) ? value : new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function showView(viewName) {
  const titles = { overview: "Overview", products: "Products", orders: "Orders", customers: "Customers", categories: "Categories", outlets: "Outlets", settings: "Settings" };
  document.querySelectorAll(".admin-tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.view === viewName));
  document.querySelectorAll(".admin-view").forEach((view) => { view.hidden = view.id !== `${viewName}-view`; });
  document.querySelector("#view-title").textContent = titles[viewName];
  clearError(dashboardError);
}

function fillProductForm(product = null) {
  editingProductId = product?.id || null;
  selectedImageFile = null;
  currentImagePath = product?.image_path || null;
  document.querySelector("#product-image").value = "";
  const categoryOptions = document.querySelector("#category-options");
  categoryOptions.replaceChildren(...categories.filter((category) => category.active).map((category) => {
    const option = document.createElement("option");
    option.value = category.name;
    return option;
  }));
  if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
  previewObjectUrl = null;
  renderImagePreview(product?.image_url || null);
  document.querySelector("#product-dialog-title").textContent = product ? "Edit product" : "Add product";
  productForm.elements.name.value = product?.name || "";
  productForm.elements.name_ar.value = product?.name_ar || "";
  productForm.elements.description.value = product?.description || "";
  productForm.elements.description_ar.value = product?.description_ar || "";
  productForm.elements.category.value = product?.category || "Storage";
  productForm.elements.category_ar.value = product?.category_ar || "";
  productForm.elements.price.value = product ? product.price.toFixed(2) : "0.00";
  productForm.elements.stock_quantity.value = product?.stock_quantity ?? 0;
  productForm.elements.art.value = product?.art || "basket";
  productForm.elements.color.value = product?.color || "#648b75";
  productForm.elements.background_color.value = product?.bg || "#e4eee6";
  productForm.elements.badge.value = product?.badge || "";
  productForm.elements.note.value = product?.note || "";
  productForm.elements.active.checked = product?.active ?? true;
  clearError(document.querySelector("#product-error"));
}

function productPayload() {
  return {
    name: productForm.elements.name.value.trim(),
    name_ar: productForm.elements.name_ar.value.trim(),
    description: productForm.elements.description.value.trim(),
    description_ar: productForm.elements.description_ar.value.trim(),
    category: productForm.elements.category.value.trim(),
    category_ar: productForm.elements.category_ar.value.trim(),
    price_cents: Math.round(Number(productForm.elements.price.value) * 100),
    stock_quantity: Number(productForm.elements.stock_quantity.value),
    art: productForm.elements.art.value,
    color: productForm.elements.color.value,
    background_color: productForm.elements.background_color.value,
    badge: productForm.elements.badge.value.trim(),
    note: productForm.elements.note.value.trim(),
    image_path: currentImagePath,
    active: productForm.elements.active.checked
  };
}

function renderImagePreview(source) {
  const image = document.querySelector("#product-image-preview");
  const placeholder = document.querySelector("#image-preview-placeholder");
  image.hidden = !source;
  placeholder.hidden = Boolean(source);
  if (source) image.src = source;
  else image.removeAttribute("src");
}

async function uploadSelectedImage() {
  if (!selectedImageFile) return;
  const result = await uploadImage(selectedImageFile);
  currentImagePath = result.image_path;
  selectedImageFile = null;
}

async function uploadImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  return api("/api/admin/uploads", { method: "POST", body: formData });
}

async function refreshAfterMutation(message) {
  await loadDashboardData();
  notify(message);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#login-error");
  clearError(error);
  const button = loginForm.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const values = new FormData(loginForm);
    const result = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ username: values.get("username"), password: values.get("password") })
    });
    csrfToken = result.csrf_token;
    showDashboard(result.username);
    loginForm.reset();
    await loadDashboardData();
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Sign-in failed.");
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    await api("/api/admin/logout", { method: "POST" });
  } catch {
    // Clear the visible session even if the network is unavailable.
  }
  showLogin();
  loginForm.elements.username.focus();
});

document.querySelectorAll(".admin-tab").forEach((tab) => tab.addEventListener("click", () => showView(tab.dataset.view)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.go)));
document.querySelector("#product-search").addEventListener("input", renderProducts);
document.querySelector("#product-status-filter").addEventListener("change", renderProducts);
document.querySelector("#low-stock-only").addEventListener("change", renderProducts);
document.querySelector("#order-status-filter").addEventListener("change", renderOrders);
document.querySelector("#customer-search").addEventListener("input", renderCustomers);
document.querySelector("#product-image").addEventListener("change", (event) => {
  const file = event.currentTarget.files[0];
  if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
  previewObjectUrl = null;
  selectedImageFile = null;
  if (!file) {
    renderImagePreview(currentImagePath ? products.find((item) => item.id === editingProductId)?.image_url : null);
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    event.currentTarget.value = "";
    showError(document.querySelector("#product-error"), "Choose an image up to 5 MB. The server will verify its format.");
    return;
  }
  clearError(document.querySelector("#product-error"));
  selectedImageFile = file;
  previewObjectUrl = URL.createObjectURL(file);
  renderImagePreview(previewObjectUrl);
});
document.querySelector("#store-logo-file").addEventListener("change", (event) => {
  const file = event.currentTarget.files[0];
  if (storeLogoPreviewObjectUrl) URL.revokeObjectURL(storeLogoPreviewObjectUrl);
  storeLogoPreviewObjectUrl = null;
  selectedStoreLogoFile = null;
  if (!file) {
    renderStoreLogoPreview(settings.logo_url || null);
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    event.currentTarget.value = "";
    showError(document.querySelector("#settings-error"), "Choose a logo image up to 5 MB. The server will verify its format.");
    return;
  }
  clearError(document.querySelector("#settings-error"));
  selectedStoreLogoFile = file;
  storeLogoPreviewObjectUrl = URL.createObjectURL(file);
  renderStoreLogoPreview(storeLogoPreviewObjectUrl);
});
document.querySelector("#remove-store-logo").addEventListener("click", () => {
  selectedStoreLogoFile = null;
  currentStoreLogoPath = null;
  document.querySelector("#store-logo-file").value = "";
  if (storeLogoPreviewObjectUrl) URL.revokeObjectURL(storeLogoPreviewObjectUrl);
  storeLogoPreviewObjectUrl = null;
  renderStoreLogoPreview(null);
});
document.querySelector("#store-cover-file").addEventListener("change", (event) => {
  const file = event.currentTarget.files[0];
  if (storeCoverPreviewObjectUrl) URL.revokeObjectURL(storeCoverPreviewObjectUrl);
  storeCoverPreviewObjectUrl = null;
  selectedStoreCoverFile = null;
  if (!file) {
    renderStoreCoverPreview(settings.cover_url || null);
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    event.currentTarget.value = "";
    showError(document.querySelector("#settings-error"), "Choose a cover image up to 5 MB. The server will verify its format.");
    return;
  }
  clearError(document.querySelector("#settings-error"));
  selectedStoreCoverFile = file;
  storeCoverPreviewObjectUrl = URL.createObjectURL(file);
  renderStoreCoverPreview(storeCoverPreviewObjectUrl);
});
document.querySelector("#remove-store-cover").addEventListener("click", () => {
  selectedStoreCoverFile = null;
  currentStoreCoverPath = null;
  document.querySelector("#store-cover-file").value = "";
  if (storeCoverPreviewObjectUrl) URL.revokeObjectURL(storeCoverPreviewObjectUrl);
  storeCoverPreviewObjectUrl = null;
  renderStoreCoverPreview(null);
});
document.querySelector("#owner-image-file").addEventListener("change", (event) => {
  const file = event.currentTarget.files[0];
  if (ownerImagePreviewObjectUrl) URL.revokeObjectURL(ownerImagePreviewObjectUrl);
  ownerImagePreviewObjectUrl = null;
  selectedOwnerImageFile = null;
  if (!file) {
    renderOwnerImagePreview(settings.owner_image_url || null);
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    event.currentTarget.value = "";
    showError(document.querySelector("#settings-error"), "Choose an owner image up to 5 MB. The server will verify its format.");
    return;
  }
  clearError(document.querySelector("#settings-error"));
  selectedOwnerImageFile = file;
  ownerImagePreviewObjectUrl = URL.createObjectURL(file);
  renderOwnerImagePreview(ownerImagePreviewObjectUrl);
});
document.querySelector("#remove-owner-image").addEventListener("click", () => {
  selectedOwnerImageFile = null;
  currentOwnerImagePath = null;
  document.querySelector("#owner-image-file").value = "";
  if (ownerImagePreviewObjectUrl) URL.revokeObjectURL(ownerImagePreviewObjectUrl);
  ownerImagePreviewObjectUrl = null;
  renderOwnerImagePreview(null);
});
document.querySelector("#add-product-button").addEventListener("click", () => {
  fillProductForm();
  productDialog.showModal();
  productForm.elements.name.focus();
});
document.querySelector("#products-table").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-product]");
  const archiveButton = event.target.closest("[data-archive-product]");
  const stockButton = event.target.closest("[data-stock-change]");
  if (stockButton) {
    const product = products.find((item) => item.id === stockButton.dataset.stockProduct);
    if (!product) return;
    const stockQuantity = Math.max(0, product.stock_quantity + Number(stockButton.dataset.stockChange));
    try {
      await api(`/api/admin/products/${encodeURIComponent(product.id)}/stock`, {
        method: "PATCH",
        body: JSON.stringify({ stock_quantity: stockQuantity })
      });
      await refreshAfterMutation("Inventory updated.");
    } catch (error) {
      showError(dashboardError, error instanceof Error ? error.message : "Could not update inventory.");
    }
  }
  if (editButton) {
    const product = products.find((item) => item.id === editButton.dataset.editProduct);
    if (product) {
      fillProductForm(product);
      productDialog.showModal();
      productForm.elements.name.focus();
    }
  }
  if (archiveButton && window.confirm("Archive this product? It will no longer appear in the storefront.")) {
    try {
      await api(`/api/admin/products/${encodeURIComponent(archiveButton.dataset.archiveProduct)}`, { method: "DELETE" });
      await refreshAfterMutation("Product archived.");
    } catch (error) {
      showError(dashboardError, error instanceof Error ? error.message : "Could not archive product.");
    }
  }
});
document.querySelector("#orders-table").addEventListener("click", (event) => {
  const detailButton = event.target.closest("[data-order-detail]");
  if (detailButton) openOrderDetails(detailButton.dataset.orderDetail);
});
document.querySelector("#customers-table").addEventListener("click", (event) => {
  const detailButton = event.target.closest("[data-customer-order-detail]");
  if (detailButton) openOrderDetails(detailButton.dataset.customerOrderDetail);
});
document.querySelector("#orders-table").addEventListener("change", async (event) => {
  const select = event.target.closest("[data-order-status]");
  if (!select || !select.value) return;
  try {
    await api(`/api/admin/orders/${encodeURIComponent(select.dataset.orderStatus)}`, {
      method: "PATCH",
      body: JSON.stringify({ status: select.value })
    });
    await refreshAfterMutation(`Order marked ${select.value}.`);
  } catch (error) {
    showError(dashboardError, error instanceof Error ? error.message : "Could not update order.");
    await loadDashboardData();
  }
});

document.querySelector("#category-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#category-error");
  clearError(error);
  try {
    await api("/api/admin/categories", {
      method: "POST",
      body: JSON.stringify({ name: form.elements.name.value.trim(), name_ar: form.elements.name_ar.value.trim() })
    });
    form.reset();
    await refreshAfterMutation("Category added.");
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Could not add category.");
  }
});
document.querySelector("#category-list").addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-rename-category]");
  if (!form) return;
  event.preventDefault();
  const error = document.querySelector("#category-error");
  clearError(error);
  try {
    await api(`/api/admin/categories/${form.dataset.renameCategory}`, {
      method: "PUT",
      body: JSON.stringify({ name: form.elements.name.value.trim(), name_ar: form.elements.name_ar.value.trim() })
    });
    await refreshAfterMutation("Category renamed.");
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Could not rename category.");
  }
});
document.querySelector("#category-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-archive-category]");
  if (!button || !window.confirm("Remove this category? It must not contain products.")) return;
  const error = document.querySelector("#category-error");
  clearError(error);
  try {
    await api(`/api/admin/categories/${button.dataset.archiveCategory}`, { method: "DELETE" });
    await refreshAfterMutation("Category removed.");
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Could not remove category.");
  }
});
document.querySelector("#outlet-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#outlet-error");
  clearError(error);
  try {
    const values = new FormData(form);
    const outlet = Object.fromEntries(["name_en", "name_ar", "address_en", "address_ar", "phone", "hours_en", "hours_ar"].map((key) => [key, values.get(key)]));
    const path = editingOutletId ? `/api/admin/outlets/${editingOutletId}` : "/api/admin/outlets";
    await api(path, { method: editingOutletId ? "PUT" : "POST", body: JSON.stringify(outlet) });
    fillOutletForm();
    await refreshAfterMutation(editingOutletId ? "Outlet updated." : "Outlet added.");
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Could not save outlet.");
  }
});
document.querySelector("#cancel-outlet-edit").addEventListener("click", () => fillOutletForm());
document.querySelector("#outlet-admin-list").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-outlet]");
  const archiveButton = event.target.closest("[data-archive-outlet]");
  if (editButton) {
    const outlet = outlets.find((item) => item.id === Number(editButton.dataset.editOutlet));
    if (outlet) fillOutletForm(outlet);
  }
  if (archiveButton && window.confirm("Archive this outlet? It will no longer appear publicly.")) {
    try {
      await api(`/api/admin/outlets/${archiveButton.dataset.archiveOutlet}`, { method: "DELETE" });
      await refreshAfterMutation("Outlet archived.");
    } catch (requestError) {
      showError(document.querySelector("#outlet-error"), requestError instanceof Error ? requestError.message : "Could not archive outlet.");
    }
  }
});
document.querySelector("#settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#settings-error");
  const button = document.querySelector("#save-settings");
  clearError(error);
  button.disabled = true;
  try {
    const values = new FormData(form);
    if (selectedStoreLogoFile) {
      const uploadedLogo = await uploadImage(selectedStoreLogoFile);
      currentStoreLogoPath = uploadedLogo.image_path;
      selectedStoreLogoFile = null;
    }
    if (selectedStoreCoverFile) {
      const uploadedCover = await uploadImage(selectedStoreCoverFile);
      currentStoreCoverPath = uploadedCover.image_path;
      selectedStoreCoverFile = null;
    }
    if (selectedOwnerImageFile) {
      const uploadedOwnerImage = await uploadImage(selectedOwnerImageFile);
      currentOwnerImagePath = uploadedOwnerImage.image_path;
      selectedOwnerImageFile = null;
    }
    await api("/api/admin/settings", {
      method: "PUT",
      body: JSON.stringify({
        business_name: values.get("business_name"),
        business_name_ar: values.get("business_name_ar"),
        about_en: values.get("about_en"),
        about_ar: values.get("about_ar"),
        about_eyebrow_en: values.get("about_eyebrow_en"),
        about_title_en: values.get("about_title_en"),
        about_lead_en: values.get("about_lead_en"),
        about_story_eyebrow_en: values.get("about_story_eyebrow_en"),
        about_story_heading_en: values.get("about_story_heading_en"),
        about_story_en: values.get("about_story_en"),
        about_story_secondary_en: values.get("about_story_secondary_en"),
        about_value_1_title: values.get("about_value_1_title"),
        about_value_1_text: values.get("about_value_1_text"),
        about_value_2_title: values.get("about_value_2_title"),
        about_value_2_text: values.get("about_value_2_text"),
        about_value_3_title: values.get("about_value_3_title"),
        about_value_3_text: values.get("about_value_3_text"),
        owner_name: values.get("owner_name"),
        owner_eyebrow_en: values.get("owner_eyebrow_en"),
        owner_role: values.get("owner_role"),
        owner_bio: values.get("owner_bio"),
        owner_image_path: currentOwnerImagePath,
        about_primary_color: values.get("about_primary_color"),
        about_background_color: values.get("about_background_color"),
        about_surface_color: values.get("about_surface_color"),
        about_accent_color: values.get("about_accent_color"),
        about_values_eyebrow_en: values.get("about_values_eyebrow_en"),
        about_contact_eyebrow_en: values.get("about_contact_eyebrow_en"),
        about_contact_title_en: values.get("about_contact_title_en"),
        about_contact_text_en: values.get("about_contact_text_en"),
        currency: values.get("currency"),
        locale: values.get("locale"),
        contact_email: values.get("contact_email"),
        contact_phone: values.get("contact_phone"),
        business_address: values.get("business_address"),
        logo_path: currentStoreLogoPath,
        cover_path: currentStoreCoverPath,
        cover_fit: values.get("cover_fit"),
        low_stock_threshold: Number(values.get("low_stock_threshold"))
      })
    });
    await refreshAfterMutation("Store settings saved.");
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Could not save settings.");
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("[data-export]").forEach((button) => button.addEventListener("click", async () => {
  const kind = button.dataset.export;
  try {
    const response = await fetch(`/api/admin/exports/${kind}.csv`, { credentials: "same-origin" });
    if (!response.ok) {
      if (response.status === 401) showLogin();
      throw new Error("Could not export this data.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${kind}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    showError(dashboardError, error instanceof Error ? error.message : "Could not export this data.");
  }
}));

document.querySelector("#close-product-dialog").addEventListener("click", () => productDialog.close());
document.querySelector("#cancel-product").addEventListener("click", () => productDialog.close());
document.querySelector("#close-order-dialog").addEventListener("click", () => document.querySelector("#order-dialog").close());
document.querySelector("#close-order-details").addEventListener("click", () => document.querySelector("#order-dialog").close());
document.querySelector("#print-order").addEventListener("click", () => window.print());
productForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!productForm.reportValidity()) return;
  const error = document.querySelector("#product-error");
  clearError(error);
  const submit = document.querySelector("#save-product");
  submit.disabled = true;
  try {
    const path = editingProductId ? `/api/admin/products/${encodeURIComponent(editingProductId)}` : "/api/admin/products";
    const method = editingProductId ? "PUT" : "POST";
    await uploadSelectedImage();
    await api(path, { method, body: JSON.stringify(productPayload()) });
    productDialog.close();
    await refreshAfterMutation(editingProductId ? "Product updated." : "Product created.");
  } catch (requestError) {
    showError(error, requestError instanceof Error ? requestError.message : "Could not save product.");
  } finally {
    submit.disabled = false;
  }
});

async function initializeAdmin() {
  try {
    const config = await api("/api/config");
    currency = config.currency;
    locale = config.locale;
    const session = await api("/api/admin/session");
    if (!session.authenticated) {
      showLogin();
      return;
    }
    csrfToken = session.csrf_token;
    showDashboard(session.username);
    await loadDashboardData();
  } catch {
    showLogin();
  }
}

initializeAdmin();
