"""Theme presets for public websites. Each is a bundle of fonts + design tokens,
so the same content looks like a different site. Combined with the site's own
accent colour. Public sites are Django-served, so real Google Fonts are fine.
"""

_FONTS = "https://fonts.googleapis.com/css2?{}&display=swap"

THEMES = {
    "minimal": {
        "fonts_url": _FONTS.format("family=Inter:wght@400;500;600;700;800;900&family=Space+Grotesk:wght@600;700"),
        "font_head": "'Inter', system-ui, sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "font_brand": "'Space Grotesk', system-ui, sans-serif",
        "brand_weight": "700",
        "head_weight": "800",
        "head_spacing": "-0.03em",
        "radius": "10px",
        "btn_radius": "10px",
        "sec_pad": "72px",
        "ink": "#16181d", "muted": "#5b6472", "line": "#e8eaee",
        "bg": "#ffffff", "soft": "#f6f7f9",
        "hero_bg": "linear-gradient(180deg,color-mix(in srgb,var(--accent) 7%,#fff),#fff)",
    },
    "bold": {
        "fonts_url": _FONTS.format("family=Poppins:wght@600;700;800;900&family=Inter:wght@400;500;600&family=Unbounded:wght@600;700;800"),
        "font_head": "'Poppins', system-ui, sans-serif",
        "font_body": "'Inter', system-ui, sans-serif",
        "font_brand": "'Unbounded', system-ui, sans-serif",
        "brand_weight": "700",
        "head_weight": "800",
        "head_spacing": "-0.03em",
        "radius": "18px",
        "btn_radius": "999px",
        "sec_pad": "84px",
        "ink": "#141019", "muted": "#6b6478", "line": "#ece8f0",
        "bg": "#ffffff", "soft": "#f7f5fb",
        "hero_bg": "linear-gradient(180deg,color-mix(in srgb,var(--accent) 16%,#fff),#fff)",
    },
    "editorial": {
        "fonts_url": _FONTS.format("family=Playfair+Display:wght@600;700;800;900&family=Source+Serif+4:wght@400;500;600"),
        "font_head": "'Playfair Display', Georgia, serif",
        "font_body": "'Source Serif 4', Georgia, serif",
        "font_brand": "'Playfair Display', Georgia, serif",
        "brand_weight": "900",
        "head_weight": "700",
        "head_spacing": "-0.01em",
        "radius": "3px",
        "btn_radius": "3px",
        "sec_pad": "80px",
        "ink": "#1c1a17", "muted": "#6a6459", "line": "#e7e2d8",
        "bg": "#fffdfa", "soft": "#f6f2ea",
        "hero_bg": "linear-gradient(180deg,#f8f3ea,#fffdfa)",
    },
    "warm": {
        "fonts_url": _FONTS.format("family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Nunito:wght@400;500;600;700&family=DM+Serif+Display:ital@0;1"),
        "font_head": "'Fraunces', Georgia, serif",
        "font_body": "'Nunito', system-ui, sans-serif",
        "font_brand": "'DM Serif Display', Georgia, serif",
        "brand_weight": "400",
        "head_weight": "600",
        "head_spacing": "-0.01em",
        "radius": "20px",
        "btn_radius": "999px",
        "sec_pad": "78px",
        "ink": "#2b2620", "muted": "#7a7264", "line": "#eee6da",
        "bg": "#fffdf8", "soft": "#f8f2e8",
        "hero_bg": "linear-gradient(180deg,color-mix(in srgb,var(--accent) 12%,#fffdf8),#fffdf8)",
    },
    "tech": {
        "fonts_url": _FONTS.format("family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=Sora:wght@700;800"),
        "font_head": "'Space Grotesk', system-ui, sans-serif",
        "font_body": "'IBM Plex Sans', system-ui, sans-serif",
        "font_brand": "'Sora', system-ui, sans-serif",
        "brand_weight": "800",
        "head_weight": "700",
        "head_spacing": "-0.02em",
        "radius": "8px",
        "btn_radius": "8px",
        "sec_pad": "76px",
        "ink": "#12151b", "muted": "#5c6470", "line": "#e5e8ee",
        "bg": "#ffffff", "soft": "#f4f6fa",
        "hero_bg": "linear-gradient(180deg,color-mix(in srgb,var(--accent) 9%,#fff),#fff)",
    },
}

DEFAULT = "minimal"


def theme_for(site):
    return THEMES.get(getattr(site, "theme", DEFAULT), THEMES[DEFAULT])
