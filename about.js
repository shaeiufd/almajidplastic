function setText(selector, value) {
  const element = document.querySelector(selector);
  if (element && value) element.textContent = value;
}

async function loadAboutPage() {
  try {
    const [configResponse, outletsResponse] = await Promise.all([fetch("/api/config"), fetch("/api/outlets")]);
    if (!configResponse.ok || !outletsResponse.ok) return;
    const config = await configResponse.json();
    const outlets = await outletsResponse.json();
    const businessName = config.business_name || "Al Majid Plastic";
    document.title = `About us | ${businessName}`;
    setText("#header-business-name", businessName);
    setText("#footer-business-name", businessName);
    setText(".about-hero .eyebrow [data-about-eyebrow]", config.about_eyebrow_en);
    setText("#about-lead", config.about_lead_en || config.about_en);
    setText("#about-story-eyebrow", config.about_story_eyebrow_en);
    setText("#about-story-heading", config.about_story_heading_en);
    setText("#about-story", config.about_story_en || config.about_en);
    setText("#about-story-secondary", config.about_story_secondary_en);
    setText("#owner-name", config.owner_name || "Our owner");
    setText("#owner-eyebrow", config.owner_eyebrow_en);
    setText("#owner-role", config.owner_role || "Founder and owner");
    setText("#owner-bio", config.owner_bio || "Al Majid Plastic is built around a simple idea: useful products, dependable service, and a store people can return to with confidence.");
    setText("#value-1-title", config.about_value_1_title);
    setText("#value-1-text", config.about_value_1_text);
    setText("#value-2-title", config.about_value_2_title);
    setText("#value-2-text", config.about_value_2_text);
    setText("#value-3-title", config.about_value_3_title);
    setText("#value-3-text", config.about_value_3_text);
    setText("#about-values-eyebrow", config.about_values_eyebrow_en);
    setText("#about-contact-eyebrow", config.about_contact_eyebrow_en);
    setText("#about-contact-title", config.about_contact_title_en);
    setText("#about-contact-text", config.about_contact_text_en);
    const root = document.documentElement;
    for (const [variable, value] of [["--about-primary", config.about_primary_color], ["--about-background", config.about_background_color], ["--about-surface", config.about_surface_color], ["--about-accent", config.about_accent_color]]) {
      if (value) root.style.setProperty(variable, value);
    }
    if (config.owner_image_url) {
      const image = document.querySelector("#owner-image");
      image.src = config.owner_image_url;
      image.alt = config.owner_name ? `${config.owner_name}, owner` : "Owner portrait";
      image.hidden = false;
      document.querySelector("#owner-image-placeholder").hidden = true;
    }
    setText("#about-contact-email", config.contact_email || "Email us for support");
    setText("#about-contact-phone", config.contact_phone || (outlets[0]?.phone || "Our team is ready to help"));
  } catch {
    // The page keeps its carefully written defaults if the store API is unavailable.
  }
}

document.querySelector("#about-year").textContent = new Date().getFullYear();
loadAboutPage();
