let products = [];
let money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const grid = document.querySelector("#product-grid");
const searchInput = document.querySelector("#search");
const sortSelect = document.querySelector("#sort-products");
const countLabel = document.querySelector("#result-count");
const emptyState = document.querySelector("#empty-state");
const overlay = document.querySelector("#overlay");
const drawer = document.querySelector("#cart-drawer");
const cartItems = document.querySelector("#cart-items");
const cartEmpty = document.querySelector("#cart-empty");
const cartFooter = document.querySelector("#cart-footer");
const toast = document.querySelector("#toast");
let activeCategory = "All products";
let favoritesOnly = false;
let toastTimer;
let cart = loadCart();
let favorites = new Set(loadFavorites());

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function loadCart() {
  try {
    const saved = JSON.parse(localStorage.getItem("al-majid-cart") || "[]");
    return Array.isArray(saved) ? saved.filter((entry) => typeof entry.id === "string" && Number.isInteger(entry.quantity) && entry.quantity > 0) : [];
  } catch {
    return [];
  }
}

function loadFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem("al-majid-favorites") || "[]");
    return Array.isArray(saved) ? saved.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function saveFavorites() {
  try {
    localStorage.setItem("al-majid-favorites", JSON.stringify([...favorites]));
  } catch {
    showToast("Saved items are only available for this visit.");
  }
}

function saveCart() {
  try {
    localStorage.setItem("al-majid-cart", JSON.stringify(cart));
  } catch {
    showToast("Basket saved for this visit.");
  }
}

function filteredProducts() {
  const query = searchInput.value.trim().toLowerCase();
  const matches = products.filter((product) => {
    const categoryMatch = activeCategory === "All products" || product.category === activeCategory;
    const textMatch = `${product.name} ${product.category} ${product.note} ${product.description}`.toLowerCase().includes(query);
    return categoryMatch && textMatch;
  });
  const sort = sortSelect.value;
  if (sort === "price-low") matches.sort((first, second) => first.price - second.price);
  if (sort === "price-high") matches.sort((first, second) => second.price - first.price);
  if (sort === "name") matches.sort((first, second) => first.name.localeCompare(second.name));
  return matches;
}

function renderProducts() {
  const matches = filteredProducts().filter((product) => !favoritesOnly || favorites.has(product.id));
  grid.innerHTML = matches.map((product) => `
    <article class="product-card" style="--product-color:${product.color};--visual-bg:${product.bg}">
      <div class="product-visual visual-${product.art}${product.image_url ? " has-photo" : ""}">
        <span class="product-badge" aria-hidden="true">${escapeHTML(product.badge)}</span>
        ${product.image_url ? `<img class="product-photo" src="${escapeHTML(product.image_url)}" alt="" loading="lazy" />` : '<span class="shape-main" aria-hidden="true"></span><span class="shape-detail" aria-hidden="true"></span><span class="shape-accent" aria-hidden="true"></span>'}
        <button class="favorite-toggle${favorites.has(product.id) ? " is-favorite" : ""}" type="button" data-favorite="${escapeHTML(product.id)}" aria-pressed="${favorites.has(product.id)}" aria-label="${favorites.has(product.id) ? "Remove" : "Add"} ${escapeHTML(product.name)} ${favorites.has(product.id) ? "from" : "to"} favorites">${favorites.has(product.id) ? "&#9829;" : "&#9825;"}</button>
        <button class="quick-add" type="button" data-add="${escapeHTML(product.id)}" aria-label="Add ${escapeHTML(product.name)} to basket">+</button>
      </div>
      <div class="product-info">
        <p class="product-category">${escapeHTML(product.category)}</p>
        <h3 class="product-title">${escapeHTML(product.name)}</h3>
        <div class="product-bottom"><span class="product-price">${money.format(product.price)}<span class="product-unit">/ each</span></span><span class="product-color-note">${escapeHTML(product.note)}</span></div>
        <button class="product-detail-button" type="button" data-view-product="${escapeHTML(product.id)}">View details</button>
      </div>
    </article>`).join("");
  countLabel.textContent = `${matches.length} ${matches.length === 1 ? "useful find" : "useful finds"}`;
  document.querySelector("#all-product-count").textContent = products.length;
  renderFavoritesButton();
  emptyState.hidden = matches.length > 0;
  grid.hidden = matches.length === 0;
}

function renderFavoritesButton() {
  const button = document.querySelector("#toggle-favorites");
  const count = document.querySelector("#favorites-count");
  count.textContent = favorites.size;
  button.setAttribute("aria-pressed", String(favoritesOnly));
  button.setAttribute("aria-label", `${favoritesOnly ? "Show all products" : "Show favorites"}, ${favorites.size} saved`);
  button.classList.toggle("is-active", favoritesOnly);
}

function setBrandLogo(source) {
  for (const [markId, imageId] of [["header-brand-mark", "header-brand-image"], ["footer-brand-mark", "footer-brand-image"]]) {
    const mark = document.getElementById(markId);
    const image = document.getElementById(imageId);
    image.hidden = !source;
    mark.classList.toggle("has-logo", Boolean(source));
    if (source) image.src = source;
    else image.removeAttribute("src");
  }
}

function toggleFavorite(id) {
  if (favorites.has(id)) favorites.delete(id);
  else favorites.add(id);
  saveFavorites();
  renderProducts();
}

function openProductDetails(id) {
  const product = products.find((item) => item.id === id);
  if (!product) return;
  const art = product.image_url
    ? `<img class="product-detail-photo" src="${escapeHTML(product.image_url)}" alt="${escapeHTML(product.name)}" />`
    : `<div class="product-visual product-detail-art visual-${product.art}" style="--product-color:${product.color};--visual-bg:${product.bg}" aria-hidden="true"><span class="shape-main"></span><span class="shape-detail"></span><span class="shape-accent"></span></div>`;
  document.querySelector("#product-detail-content").innerHTML = `
    <div class="product-detail-visual">${art}</div>
    <div class="product-detail-copy">
      <p class="product-category">${escapeHTML(product.category)}</p>
      <h2 id="product-detail-title">${escapeHTML(product.name)}</h2>
      <p class="product-detail-description">${escapeHTML(product.description || "A practical everyday essential for your home.")}</p>
      <p class="product-detail-stock">${product.stock_quantity > 0 ? `${product.stock_quantity} in stock` : "Currently out of stock"}</p>
      <strong class="product-detail-price">${money.format(product.price)}</strong>
      <div class="product-detail-actions">
        <button class="checkout-button" type="button" data-detail-add="${escapeHTML(product.id)}" ${product.stock_quantity < 1 ? "disabled" : ""}>Add to basket <span aria-hidden="true">&#8594;</span></button>
        <button class="detail-favorite${favorites.has(product.id) ? " is-favorite" : ""}" type="button" data-detail-favorite="${escapeHTML(product.id)}" aria-pressed="${favorites.has(product.id)}">${favorites.has(product.id) ? "Remove from favorites" : "Save to favorites"}</button>
      </div>
    </div>`;
  document.querySelector("#product-detail-dialog").showModal();
}

function renderCategories(categoryRows) {
  const nav = document.querySelector(".nav-inner");
  const navNote = nav.querySelector(".nav-note");
  const filters = document.querySelector(".filter-list");
  nav.querySelectorAll('.nav-category:not([data-category="All products"])').forEach((button) => button.remove());
  filters.querySelectorAll('.filter-chip:not([data-category="All products"])').forEach((button) => button.remove());
  categoryRows.forEach((category) => {
    const navButton = document.createElement("button");
    navButton.className = "nav-category";
    navButton.type = "button";
    navButton.dataset.category = category.name;
    navButton.textContent = category.name;
    nav.insertBefore(navButton, navNote);

    const filterButton = document.createElement("button");
    filterButton.className = "filter-chip";
    filterButton.type = "button";
    filterButton.dataset.category = category.name;
    filterButton.textContent = category.name;
    filters.append(filterButton);
  });
}

function setCategory(category) {
  activeCategory = category;
  document.querySelectorAll("[data-category]").forEach((button) => {
    const selected = button.dataset.category === category;
    button.classList.toggle("is-active", selected && button.classList.contains("nav-category"));
    button.classList.toggle("is-selected", selected && button.classList.contains("filter-chip"));
    if (button.classList.contains("nav-category")) button.setAttribute("aria-current", selected ? "true" : "false");
  });
  renderProducts();
}

function cartQuantity() {
  return cart.reduce((total, entry) => total + entry.quantity, 0);
}

function addToCart(id) {
  const product = products.find((item) => item.id === id);
  if (!product) return;
  if (product.stock_quantity < 1) {
    showToast("This item is currently out of stock.");
    return;
  }
  const existing = cart.find((entry) => entry.id === id);
  if (existing?.quantity >= product.stock_quantity) {
    showToast("There is no more stock available for this item.");
    return;
  }
  if (existing) existing.quantity += 1;
  else cart.push({ id, quantity: 1 });
  saveCart();
  renderCart();
  showToast(`${product.name} added to your basket.`);
}

function changeQuantity(id, change) {
  const entry = cart.find((item) => item.id === id);
  if (!entry) return;
  const product = products.find((item) => item.id === id);
  if (change > 0 && entry.quantity >= product.stock_quantity) {
    showToast("There is no more stock available for this item.");
    return;
  }
  entry.quantity += change;
  if (entry.quantity < 1) cart = cart.filter((item) => item.id !== id);
  saveCart();
  renderCart();
}

function removeFromCart(id) {
  cart = cart.filter((entry) => entry.id !== id);
  saveCart();
  renderCart();
}

function renderCart() {
  const quantity = cartQuantity();
  document.querySelector("#basket-count").textContent = quantity;
  document.querySelector("#open-cart").setAttribute("aria-label", `Open basket, ${quantity} ${quantity === 1 ? "item" : "items"}`);
  document.querySelector("#drawer-count").textContent = `(${quantity})`;
  cartEmpty.hidden = quantity > 0;
  cartItems.hidden = quantity === 0;
  cartFooter.hidden = quantity === 0;
  const subtotal = cart.reduce((sum, entry) => {
    const product = products.find((item) => item.id === entry.id);
    return sum + product.price * entry.quantity;
  }, 0);
  document.querySelector("#cart-subtotal").textContent = money.format(subtotal);
  cartItems.innerHTML = cart.map((entry) => {
    const product = products.find((item) => item.id === entry.id);
    return `
      <article class="cart-row" style="--product-color:${product.color};--visual-bg:${product.bg}">
        <div class="cart-thumb" aria-hidden="true">${product.image_url ? `<img src="${escapeHTML(product.image_url)}" alt="" />` : "<span></span>"}</div>
        <div>
          <h3 class="cart-product-name">${escapeHTML(product.name)}</h3>
          <span class="cart-unit-price">${money.format(product.price)} each</span>
          <div class="quantity-control" aria-label="Quantity for ${escapeHTML(product.name)}">
            <button type="button" data-quantity="${escapeHTML(product.id)}" data-change="-1" aria-label="Decrease ${escapeHTML(product.name)} quantity">&#8722;</button>
            <span>${entry.quantity}</span>
            <button type="button" data-quantity="${escapeHTML(product.id)}" data-change="1" aria-label="Increase ${escapeHTML(product.name)} quantity">+</button>
          </div>
        </div>
        <div class="cart-line-total">${money.format(product.price * entry.quantity)}<button class="remove-item" type="button" data-remove="${escapeHTML(product.id)}">Remove</button></div>
      </article>`;
  }).join("");
}

function openCart() {
  overlay.hidden = false;
  drawer.hidden = false;
  document.body.style.overflow = "hidden";
  drawer.querySelector("[data-close]").focus();
}

function closeOverlays() {
  overlay.hidden = true;
  drawer.hidden = true;
  document.querySelector("#checkout-modal").hidden = true;
  document.querySelector("#account-modal").hidden = true;
  document.body.style.overflow = "";
}

let accountMode = "signup";
let currentCustomer = null;

function renderAccount(customer) {
  currentCustomer = customer?.authenticated ? customer : null;
  const signedIn = Boolean(currentCustomer);
  document.querySelector("#account-auth-view").hidden = signedIn;
  document.querySelector("#account-signed-in").hidden = !signedIn;
  document.querySelector("#account-label").textContent = signedIn ? "Account" : "Sign in";
  if (signedIn) {
    document.querySelector("#account-user-name").textContent = currentCustomer.full_name;
    document.querySelector("#account-user-email").textContent = currentCustomer.email;
  }
}

function setAccountMode(mode) {
  accountMode = mode;
  const signup = mode === "signup";
  document.querySelector("#account-name-field").hidden = !signup;
  document.querySelector("#account-name-field input").required = signup;
  document.querySelector("#account-submit").innerHTML = `${signup ? "Create account" : "Sign in"} <span aria-hidden="true">&#8594;</span>`;
  document.querySelector("#account-switch").textContent = signup ? "Already have an account? Sign in" : "New here? Create an account";
  document.querySelector("#account-form input[type=password]").autocomplete = signup ? "new-password" : "current-password";
}

function openAccount() {
  overlay.hidden = false;
  document.querySelector("#account-modal").hidden = false;
  document.body.style.overflow = "hidden";
  if (!currentCustomer) document.querySelector("#account-form input").focus();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (button) setCategory(button.dataset.category);
});
searchInput.addEventListener("input", renderProducts);
sortSelect.addEventListener("change", renderProducts);
grid.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add]");
  const favoriteButton = event.target.closest("[data-favorite]");
  const detailButton = event.target.closest("[data-view-product]");
  if (favoriteButton) toggleFavorite(favoriteButton.dataset.favorite);
  if (detailButton) openProductDetails(detailButton.dataset.viewProduct);
  if (addButton) addToCart(addButton.dataset.add);
});
document.querySelector("#product-detail-content").addEventListener("click", (event) => {
  const favoriteButton = event.target.closest("[data-detail-favorite]");
  const addButton = event.target.closest("[data-detail-add]");
  if (favoriteButton) {
    toggleFavorite(favoriteButton.dataset.detailFavorite);
    openProductDetails(favoriteButton.dataset.detailFavorite);
  }
  if (addButton) addToCart(addButton.dataset.detailAdd);
});
document.querySelector("#toggle-favorites").addEventListener("click", () => {
  favoritesOnly = !favoritesOnly;
  renderProducts();
});
document.querySelector("#close-product-detail").addEventListener("click", () => document.querySelector("#product-detail-dialog").close());
cartItems.addEventListener("click", (event) => {
  const quantityButton = event.target.closest("[data-quantity]");
  const removeButton = event.target.closest("[data-remove]");
  if (quantityButton) changeQuantity(quantityButton.dataset.quantity, Number(quantityButton.dataset.change));
  if (removeButton) removeFromCart(removeButton.dataset.remove);
});
document.querySelector("#open-cart").addEventListener("click", openCart);
document.querySelector("#open-account").addEventListener("click", openAccount);
document.querySelector("#account-switch").addEventListener("click", () => setAccountMode(accountMode === "signup" ? "login" : "signup"));
document.querySelector("#account-logout").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  renderAccount(null);
  closeOverlays();
  showToast("You have been signed out.");
});
document.querySelector("#account-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#account-error");
  const submit = document.querySelector("#account-submit");
  submit.disabled = true;
  error.hidden = true;
  const values = Object.fromEntries(new FormData(form).entries());
  try {
    const response = await fetch(accountMode === "signup" ? "/api/auth/signup" : "/api/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "We could not sign you in.");
    renderAccount(result);
    form.reset();
    showToast(accountMode === "signup" ? "Your account is ready." : "Welcome back.");
  } catch (submitError) {
    error.textContent = submitError instanceof Error ? submitError.message : "We could not sign you in.";
    error.hidden = false;
  } finally {
    submit.disabled = false;
  }
});
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", closeOverlays));
overlay.addEventListener("click", closeOverlays);
document.querySelector("#checkout-button").addEventListener("click", () => {
  drawer.hidden = true;
  const modal = document.querySelector("#checkout-modal");
  document.querySelector("#order-total").textContent = money.format(cart.reduce((sum, entry) => {
    const product = products.find((item) => item.id === entry.id);
    return sum + product.price * entry.quantity;
  }, 0));
  document.querySelector("#order-form").hidden = false;
  document.querySelector("#order-success").hidden = true;
  document.querySelector("#order-error").hidden = true;
  modal.hidden = false;
  modal.querySelector("input").focus();
});
document.querySelector("#order-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = document.querySelector("#place-order");
  const errorMessage = document.querySelector("#order-error");
  submitButton.disabled = true;
  errorMessage.hidden = true;
  try {
    const formData = new FormData(form);
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_name: formData.get("customer_name"),
        email: formData.get("email"),
        phone: formData.get("phone"),
        delivery_address: formData.get("delivery_address"),
        items: cart.map((entry) => ({ product_id: entry.id, quantity: entry.quantity }))
      })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "We could not submit your order. Please review your details.");
    cart = [];
    saveCart();
    renderCart();
    form.hidden = true;
    document.querySelector("#order-reference").textContent = result.order_number;
    document.querySelector("#order-success").hidden = false;
  } catch (error) {
    errorMessage.textContent = error instanceof Error ? error.message : "We could not submit your order. Please try again.";
    errorMessage.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});
document.querySelector("#clear-filters").addEventListener("click", () => {
  searchInput.value = "";
  favoritesOnly = false;
  setCategory("All products");
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !overlay.hidden) closeOverlays();
  if (event.key === "/" && !event.ctrlKey && !event.metaKey && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    searchInput.focus();
  }
});
document.querySelector("#year").textContent = new Date().getFullYear();

function setHeroCover(source, fit = "cover") {
  const hero = document.querySelector(".hero");
  hero.classList.toggle("has-cover", Boolean(source));
  hero.classList.toggle("cover-contain", Boolean(source) && fit === "contain");
  if (source) hero.style.setProperty("--hero-cover", `url("${source}")`);
  else hero.style.removeProperty("--hero-cover");
}

function renderStoreInformation(config, outletRows) {
  const aboutCopy = document.querySelector("#about-copy");
  aboutCopy.textContent = config.about_en || "Thoughtful everyday essentials, selected for practical homes and busy routines. Browse our collection and order directly from our local store.";

  const outletGrid = document.querySelector("#outlets-grid");
  const outletEmpty = document.querySelector("#outlets-empty");
  outletGrid.innerHTML = outletRows.map((outlet) => `
    <article class="outlet-item">
      <h3>${escapeHTML(outlet.name_en)}</h3>
      <p>${escapeHTML(outlet.address_en)}${outlet.hours_en ? `<br />${escapeHTML(outlet.hours_en)}` : ""}</p>
      ${outlet.phone ? `<a href="tel:${escapeHTML(outlet.phone)}">${escapeHTML(outlet.phone)}</a>` : ""}
    </article>
  `).join("");
  outletEmpty.hidden = outletRows.length > 0;
}

async function initializeStore() {
  try {
    const [configResponse, productsResponse, categoriesResponse, outletsResponse, customerResponse] = await Promise.all([
      fetch("/api/config"), fetch("/api/products"), fetch("/api/categories"), fetch("/api/outlets"), fetch("/api/auth/me")
    ]);
    if (!configResponse.ok || !productsResponse.ok || !categoriesResponse.ok || !outletsResponse.ok || !customerResponse.ok) throw new Error("Store API is unavailable.");
    const config = await configResponse.json();
    products = await productsResponse.json();
    const categoryRows = await categoriesResponse.json();
    const outletRows = await outletsResponse.json();
    renderAccount(await customerResponse.json());
    favorites = new Set([...favorites].filter((id) => products.some((product) => product.id === id)));
    renderCategories(categoryRows);
    setBrandLogo(config.logo_url);
    setHeroCover(config.cover_url, config.cover_fit);
    document.title = `${config.business_name} | Everyday essentials`;
    document.querySelectorAll(".brand-name").forEach((brand) => { brand.textContent = config.business_name; });
    document.querySelector("#footer-business-name").textContent = config.business_name;
    renderStoreInformation(config, outletRows);
    document.querySelector("#store-contact").textContent = [
      config.contact_email,
      config.contact_phone,
      config.business_address
    ].filter(Boolean).join(" · ");
    document.querySelector("#store-contact").textContent = document.querySelector("#store-contact").textContent.replace(String.fromCharCode(1570, 183), "·");
    document.querySelector("#store-contact").textContent = document.querySelector("#store-contact").textContent.replace(String.fromCharCode(1570, 183), String.fromCharCode(183));
    money = new Intl.NumberFormat(config.locale, { style: "currency", currency: config.currency });
    cart = cart.flatMap((entry) => {
      const product = products.find((item) => item.id === entry.id);
      if (!product || product.stock_quantity < 1) return [];
      return [{ ...entry, quantity: Math.min(entry.quantity, product.stock_quantity) }];
    });
    saveCart();
    renderProducts();
    renderCart();
  } catch {
    grid.hidden = true;
    emptyState.hidden = true;
    const error = document.querySelector("#store-error");
    error.textContent = "The store is temporarily unavailable. Please refresh in a moment.";
    error.hidden = false;
  }
}

initializeStore();
