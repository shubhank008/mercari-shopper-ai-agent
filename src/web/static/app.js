const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const send = document.querySelector("#send");
const productTemplate = document.querySelector("#product-template");
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

/** Render trusted listing data without interpreting recommendation prose. */
function renderProduct(product) {
  const card = productTemplate.content.firstElementChild.cloneNode(true);
  const track = card.querySelector(".image-track");
  const title = card.querySelector("h3");
  const kicker = card.querySelector(".product-kicker");
  const meta = card.querySelector(".product-meta");
  const link = card.querySelector(".mercari-link");

  title.textContent = product.title;
  kicker.textContent = `${priceText(product)} · ${product.condition}`;
  link.href = product.item_url;
  [
    product.seller_rating_score != null ? `Seller ${product.seller_rating_score}/5` : null,
    product.seller_total_ratings != null ? `${product.seller_total_ratings} ratings` : null,
    product.num_likes != null ? `${product.num_likes} likes` : null,
    product.source_tier,
  ].filter(Boolean).forEach((value) => {
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

/** Add recommendation metadata and visual listing cards to an assistant response. */
function addRecommendation(response) {
  const message = addMessage("assistant", response.recommendation, "Mercari Scout");
  const metadata = document.createElement("div");
  metadata.className = "recommendation-metadata";
  [
    response.provider,
    response.search_tier !== "None" ? response.search_tier : null,
    response.metrics.total_duration_ms != null ? `${Math.round(response.metrics.total_duration_ms)} ms` : null,
    response.metrics.total_turns != null ? `${response.metrics.total_turns} turns` : null,
  ].filter(Boolean).forEach((value) => {
    const tag = document.createElement("span");
    tag.textContent = value;
    metadata.append(tag);
  });
  message.append(metadata);

  if (response.products.length) {
    const grid = document.createElement("div");
    grid.className = "product-grid";
    response.products.forEach((product) => grid.append(renderProduct(product)));
    message.append(grid);
  }
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
