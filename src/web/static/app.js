const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const send = document.querySelector("#send");
const productTemplate = document.querySelector("#product-template");
const lightbox = document.querySelector("#lightbox");
const lightboxImage = document.querySelector("#lightbox-image");
const lightboxClose = document.querySelector("#lightbox-close");
const sessionId = crypto.randomUUID();

/** Append a chat bubble and return it for optional follow-up content. */
function addMessage(role, text, label) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  message.innerHTML = `<p class="message-label">${label}</p><p></p>`;
  message.querySelector("p:last-child").textContent = text;
  messages.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "end" });
  return message;
}

/** Format prices without assuming a USD value is available. */
function priceText(product) {
  if (product.price_jpy != null) return `¥${Number(product.price_jpy).toLocaleString("ja-JP")}`;
  if (product.price_usd != null) return `$${Number(product.price_usd).toFixed(2)}`;
  return "Price unavailable";
}

/** Open a product image in the accessible enlarged viewer. */
function openLightbox(url, alt) {
  lightboxImage.src = url;
  lightboxImage.alt = alt;
  lightbox.hidden = false;
  lightboxClose.focus();
  console.info("[WEB_IMAGE_LIGHTBOX_OPENED]");
}

/** Render trusted listing data with explicit shopping labels. */
function renderProduct(product) {
  const card = productTemplate.content.firstElementChild.cloneNode(true);
  const track = card.querySelector(".image-track");
  const title = card.querySelector("h3");
  const kicker = card.querySelector(".product-kicker");
  const reasoning = card.querySelector(".product-reasoning");
  const meta = card.querySelector(".product-meta");
  const link = card.querySelector(".mercari-link");

  title.textContent = product.title;
  kicker.textContent = priceText(product);
  reasoning.textContent = product.reasoning;
  link.href = product.item_url;
  [
    `Condition: ${product.condition || "Not available"}`,
    `Seller: ${product.seller_name || "Not available"}`,
    `Seller Rating: ${product.seller_rating_score != null ? `${product.seller_rating_score}/5` : "Not available"}`,
    `Total Ratings: ${product.seller_total_ratings ?? "Not available"}`,
    `Likes: ${product.num_likes ?? "Not available"}`,
  ].forEach((value) => {
    const item = document.createElement("span");
    item.textContent = value;
    meta.append(item);
  });

  if (product.image_urls.length) {
    product.image_urls.forEach((url, index) => {
      const image = document.createElement("img");
      image.src = url;
      image.alt = `${product.title}, image ${index + 1}`;
      image.loading = "lazy";
      image.tabIndex = 0;
      image.addEventListener("click", () => openLightbox(url, image.alt));
      image.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") openLightbox(url, image.alt);
      });
      track.append(image);
    });
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "image-placeholder";
    placeholder.textContent = "No product image available";
    track.append(placeholder);
  }
  return card;
}

/** Render the complete shortlist as a comparison table. */
function renderComparison(shortlist) {
  const section = document.createElement("section");
  section.className = "comparison-section";
  section.innerHTML = '<div class="section-heading"><p class="eyebrow">Shortlist comparison</p><h2>Every promising listing, side by side.</h2></div>';
  const wrapper = document.createElement("div");
  wrapper.className = "comparison-scroll";
  const table = document.createElement("table");
  table.innerHTML = '<thead><tr><th>Rank</th><th>Listing</th><th>Price</th><th>Condition</th><th>Seller</th><th>Seller Rating</th><th>Total Ratings</th><th>Likes</th><th></th></tr></thead>';
  const body = document.createElement("tbody");
  shortlist.forEach((product, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${index + 1}</td><td class="table-title"></td><td class="table-price"></td><td></td><td></td><td></td><td></td><td></td><td></td>`;
    row.querySelector(".table-title").textContent = product.title;
    row.querySelector(".table-price").textContent = priceText(product);
    const values = [product.condition || "Not available", product.seller_name || "Not available", product.seller_rating_score != null ? `${product.seller_rating_score}/5` : "Not available", product.seller_total_ratings ?? "Not available", product.num_likes ?? "Not available"];
    row.querySelectorAll("td").forEach((cell, cellIndex) => { if (cellIndex >= 3 && cellIndex <= 7) cell.textContent = values[cellIndex - 3]; });
    const link = document.createElement("a");
    link.href = product.item_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View ↗";
    row.lastElementChild.append(link);
    body.append(row);
  });
  table.append(body);
  wrapper.append(table);
  section.append(wrapper);
  return section;
}

/** Add reasoning, full comparison, and final top-three recommendation cards. */
function addRecommendation(response) {
  const message = addMessage("assistant", response.recommendation, "Mercari Scout");
  const shortlist = response.shortlist || response.products || [];
  if (shortlist.length) message.append(renderComparison(shortlist));
  const finalHeading = document.createElement("div");
  finalHeading.className = "section-heading final-heading";
  finalHeading.innerHTML = '<p class="eyebrow">Final purchase recommendation</p><h2>The three worth a closer look.</h2>';
  message.append(finalHeading);
  const grid = document.createElement("div");
  grid.className = "product-grid";
  response.products.forEach((product) => grid.append(renderProduct(product)));
  message.append(grid);
}

/** Submit a request and keep the composer available after every outcome. */
async function submitMessage(message) {
  addMessage("user", message, "You");
  const pending = document.createElement("p");
  pending.className = "status";
  pending.textContent = "Searching Mercari Japan and weighing the listings";
  messages.append(pending);
  send.disabled = true;
  input.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Request failed.");
    addRecommendation(body);
  } catch (error) {
    addMessage("assistant", error.message || "The shopping assistant could not complete that request. Please try again.", "Mercari Scout");
  } finally {
    pending.remove();
    send.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || send.disabled) return;
  input.value = "";
  await submitMessage(message);
});

input.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey) return;
  event.preventDefault();
  form.requestSubmit();
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    input.focus();
  });
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});

function closeLightbox() {
  lightbox.hidden = true;
  lightboxImage.removeAttribute("src");
}

lightboxClose.addEventListener("click", closeLightbox);
lightbox.addEventListener("click", (event) => {
  if (event.target === lightbox) closeLightbox();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !lightbox.hidden) closeLightbox();
});
