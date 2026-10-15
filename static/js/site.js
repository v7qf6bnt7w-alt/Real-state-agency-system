(() => {
  const grid = document.querySelector("#property-grid");
  const form = document.querySelector("#filters");
  const dialog = document.querySelector("#lead-dialog");
  const leadForm = document.querySelector("#lead-form");
  const errorBox = document.querySelector("#form-error");
  const moreButton = document.querySelector("#load-more");
  const config = window.ESTATE_CONFIG || {};
  let activeProperty = null;
  let currentPage = 1;
  let totalProperties = 0;
  let shownProperties = 0;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  const money = (property) => new Intl.NumberFormat(undefined, {
    style: "currency", currency: property.currency || "USD", maximumFractionDigits: 0,
  }).format(property.price);
  const primaryImage = (property) => property.media?.find((item) => item.kind === "image")?.file || "";

  async function loadProperties(append = false) {
    const params = new URLSearchParams(new FormData(form));
    const search = params.get("search");
    params.delete("search");
    if (search) params.set("search", search);
    params.set("page", String(currentPage));
    const response = await fetch(`/api/properties/?${params.toString()}`);
    if (!response.ok) throw new Error("Listings are temporarily unavailable.");
    const data = await response.json();
    const properties = Array.isArray(data) ? data : data.results || [];
    totalProperties = Array.isArray(data) ? properties.length : data.count;
    shownProperties = append ? shownProperties + properties.length : properties.length;
    const markup = properties.map((property) => {
      const image = primaryImage(property) || "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1100&q=80";
      return `<article class="property-card" data-id="${escapeHtml(property.id)}" tabindex="0" role="button" aria-label="Request information about ${escapeHtml(property.title)}">
        <div class="property-photo"><img src="${escapeHtml(image)}" alt="${escapeHtml(property.title)}" loading="lazy"><span class="property-tag">${escapeHtml(property.status.replace("_", " "))}</span></div>
        <div class="property-info"><div class="property-city">${escapeHtml([property.city, property.region].filter(Boolean).join(" · "))}</div><h3 class="property-title">${escapeHtml(property.title)}</h3>
        <div class="property-meta"><span>${property.bedrooms} beds &nbsp;·&nbsp; ${property.bathrooms} baths &nbsp;·&nbsp; ${property.area_sqm} m²</span><span class="property-price">${escapeHtml(money(property))}</span></div></div>
      </article>`;
    }).join("");
    if (append) grid.insertAdjacentHTML("beforeend", markup);
    else grid.innerHTML = markup;
    document.querySelector("#result-count").textContent = `Showing ${shownProperties} of ${totalProperties} homes`;
    document.querySelector("#empty-state").hidden = totalProperties !== 0;
    moreButton.hidden = shownProperties >= totalProperties;
  }

  function addHotspotViewer(property) {
    const plans = property.floor_plans || [];
    if (!plans.length) return "";
    const plan = plans[0];
    const imageUrl = escapeHtml(plan.image);
    const hotspots = (plan.hotspots || []).map((hotspot) =>
      `<button type="button" class="hotspot" style="left:${hotspot.x}%;top:${hotspot.y}%;width:${hotspot.width}%;height:${hotspot.height}%" title="${escapeHtml(hotspot.label)}" data-details="${escapeHtml(hotspot.details || "")}" aria-label="${escapeHtml(hotspot.label)}">${escapeHtml(hotspot.label)}</button>`
    ).join("");
    return `<section class="detail-floorplan"><h3>${escapeHtml(plan.title)}</h3><div class="floorplan-image"><img src="${imageUrl}" alt="${escapeHtml(plan.title)}">${hotspots}</div><p class="room-detail" aria-live="polite">Select a room to see its details.</p></section>`;
  }

  async function openProperty(id) {
    const response = await fetch(`/api/properties/${encodeURIComponent(id)}/`);
    if (!response.ok) throw new Error("This property is temporarily unavailable. Please try again.");
    activeProperty = await response.json();
    document.querySelector("#lead-property-title").textContent = `${activeProperty.title} · ${money(activeProperty)}`;
    const assets = (activeProperty.media || []).map((item) => {
      if (item.kind === "image" && item.file) return `<img src="${escapeHtml(item.file)}" alt="${escapeHtml(item.caption || activeProperty.title)}" loading="lazy">`;
      if (item.kind === "video" && item.file) return `<video controls preload="none" aria-label="${escapeHtml(item.caption || "Property video")}"><source src="${escapeHtml(item.file)}"></video>`;
      if (item.kind === "video" && item.external_url) return `<a class="external-video" href="${escapeHtml(item.external_url)}" target="_blank" rel="noopener noreferrer">▶ Watch property video ↗</a>`;
      if (item.kind === "brochure" && item.file) return `<a class="brochure-link" href="${escapeHtml(item.file)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.caption || "View property brochure")} ↗</a>`;
      return "";
    }).join("");
    const whatsappNumber = (config.whatsapp || "").replace(/\D/g, "");
    const whatsappUrl = whatsappNumber
      ? `https://wa.me/${encodeURIComponent(whatsappNumber)}?text=${encodeURIComponent(`Hello, I'm interested in ${activeProperty.title} (Property ID: ${activeProperty.id})`)}`
      : "";
    document.querySelector("#property-detail").innerHTML = `
      <p class="detail-description">${escapeHtml(activeProperty.description)}</p>
      <p class="detail-address">${escapeHtml([activeProperty.address, activeProperty.city, activeProperty.region].filter(Boolean).join(", "))}</p>
      ${activeProperty.amenities?.length ? `<p class="detail-amenities">${activeProperty.amenities.map(escapeHtml).join(" · ")}</p>` : ""}
      ${assets ? `<div class="detail-gallery">${assets}</div>` : ""}
      ${whatsappUrl ? `<a class="whatsapp-button" href="${whatsappUrl}" target="_blank" rel="noopener noreferrer">Chat about this home on WhatsApp ↗</a>` : ""}`;
    document.querySelector("#lead-form").hidden = false;
    document.querySelector("#lead-success").hidden = true;
    errorBox.textContent = "";
    document.querySelector(".detail-floorplan")?.remove();
    const floorplanMarkup = addHotspotViewer(activeProperty);
    if (floorplanMarkup) document.querySelector("#property-detail")?.insertAdjacentHTML("beforeend", floorplanMarkup);
    dialog.showModal();
  }

  function showCatalogError(error) {
    const catalogError = document.querySelector("#catalog-error");
    catalogError.textContent = error.message || "We could not load this property.";
    catalogError.hidden = false;
  }

  dialog.addEventListener("click", (event) => {
    if (event.target.closest(".hotspot")) {
      const hotspot = event.target.closest(".hotspot");
      const details = hotspot.dataset.details;
      document.querySelector(".room-detail").textContent = `${hotspot.title}${details ? `: ${details}` : ""}`;
    }
  });
  grid.addEventListener("click", (event) => {
    if (event.target.closest(".hotspot")) {
      return;
    }
    const card = event.target.closest(".property-card");
    if (card) openProperty(card.dataset.id).catch(showCatalogError);
  });
  grid.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches(".property-card")) {
      event.preventDefault();
      openProperty(event.target.dataset.id).catch(showCatalogError);
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    currentPage = 1;
    shownProperties = 0;
    grid.innerHTML = '<div class="loading">Finding the right homes…</div>';
    loadProperties().catch((error) => { grid.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`; });
  });
  moreButton.addEventListener("click", () => {
    currentPage += 1;
    moreButton.disabled = true;
    loadProperties(true).catch((error) => { currentPage -= 1; grid.insertAdjacentHTML("beforeend", `<p class="empty-state">${escapeHtml(error.message)}</p>`); }).finally(() => { moreButton.disabled = false; });
  });
  document.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
  document.querySelector("#close-success").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  leadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!activeProperty) return;
    errorBox.textContent = "";
    const formData = new FormData(leadForm);
    const payload = Object.fromEntries(formData.entries());
    payload.property_id = activeProperty.id;
    try {
      if (config.recaptchaRequired) {
        if (!window.grecaptcha || !config.recaptchaSiteKey) throw new Error("Verification is not ready. Please try again.");
        payload.recaptcha_token = await window.grecaptcha.execute(config.recaptchaSiteKey, { action: "lead" });
      }
      const response = await fetch("/api/leads/public/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(Object.values(result).flat().join(" "));
      leadForm.hidden = true;
      document.querySelector("#lead-success").hidden = false;
    } catch (error) {
      errorBox.textContent = error.message || "We could not send your request. Please try again.";
    }
  });
  loadProperties().catch((error) => {
    grid.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  });
  fetch("/api/config/").then((response) => response.json()).then((value) => {
    Object.assign(config, {
      whatsapp: value.whatsapp_number || "",
      recaptchaRequired: Boolean(value.recaptcha_required),
      recaptchaSiteKey: value.recaptcha_site_key || "",
    });
    if (config.recaptchaRequired && config.recaptchaSiteKey) {
      const script = document.createElement("script");
      script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(config.recaptchaSiteKey)}`;
      script.async = true;
      document.head.append(script);
    }
  }).catch(() => {
    console.error("Could not load public platform configuration.");
  });
})();
