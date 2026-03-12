"""Ad Platform Specifications — sizes, limits, and clicktag patterns.

Comprehensive registry of ad dimensions for Meta, Google, and LinkedIn.
Used by ads_builder and kie_image_generator for multi-platform output.

Sources: Hootsuite, Google Support, LinkedIn Marketing.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────
# META (Facebook / Instagram)
# ──────────────────────────────────────────────────────────────
META_SIZES = {
    "feed_image": {
        "width": 1440, "height": 1800, "aspect_ratio": "4:5",
        "format": "jpg", "max_size_mb": 30,
        "placement": "Feed (image)",
    },
    "feed_square": {
        "width": 1080, "height": 1080, "aspect_ratio": "1:1",
        "format": "jpg", "max_size_mb": 30,
        "placement": "Feed (carré)",
    },
    "stories_reels": {
        "width": 1080, "height": 1920, "aspect_ratio": "9:16",
        "format": "jpg", "max_size_mb": 30,
        "placement": "Stories/Reels",
    },
    "carousel": {
        "width": 1080, "height": 1080, "aspect_ratio": "1:1",
        "format": "jpg", "max_size_mb": 30,
        "placement": "Carousel",
    },
    "right_column": {
        "width": 1080, "height": 1080, "aspect_ratio": "1:1",
        "format": "jpg", "max_size_mb": 30,
        "placement": "Right Column",
    },
    "feed_video": {
        "width": 1080, "height": 1350, "aspect_ratio": "4:5",
        "format": "mp4", "max_size_mb": 4096, "max_duration": 241,
        "placement": "Feed vidéo",
    },
    "instream_video": {
        "width": 1080, "height": 1080, "aspect_ratio": "16:9",
        "format": "mp4", "max_size_mb": 4096, "max_duration": 15,
        "placement": "In-Stream vidéo",
    },
}

# Meta rules: H.264, AAC 128kbps+, ratio tolerance 3%, 4:5 optimal for feed
META_RULES = {
    "video_codec": "H.264",
    "audio_codec": "AAC",
    "audio_bitrate_min": "128kbps",
    "ratio_tolerance": "3%",
    "optimal_feed_ratio": "4:5",
}

# ──────────────────────────────────────────────────────────────
# GOOGLE DISPLAY NETWORK (GDN)
# ──────────────────────────────────────────────────────────────
GOOGLE_SIZES = {
    "medium_rectangle": {
        "width": 300, "height": 250, "name": "Medium Rectangle",
        "format": "jpg", "max_size_kb": 150,
    },
    "large_rectangle": {
        "width": 336, "height": 280, "name": "Large Rectangle",
        "format": "jpg", "max_size_kb": 150,
    },
    "leaderboard": {
        "width": 728, "height": 90, "name": "Leaderboard",
        "format": "jpg", "max_size_kb": 150,
    },
    "large_leaderboard": {
        "width": 970, "height": 90, "name": "Large Leaderboard",
        "format": "jpg", "max_size_kb": 150,
    },
    "billboard": {
        "width": 970, "height": 250, "name": "Billboard",
        "format": "jpg", "max_size_kb": 150,
    },
    "skyscraper": {
        "width": 160, "height": 600, "name": "Wide Skyscraper",
        "format": "jpg", "max_size_kb": 150,
    },
    "half_page": {
        "width": 300, "height": 600, "name": "Half-Page Ad",
        "format": "jpg", "max_size_kb": 150,
    },
    "mobile_banner": {
        "width": 320, "height": 50, "name": "Mobile Banner",
        "format": "jpg", "max_size_kb": 150,
    },
    "mobile_large": {
        "width": 320, "height": 100, "name": "Large Mobile Banner",
        "format": "jpg", "max_size_kb": 150,
    },
    "banner": {
        "width": 468, "height": 60, "name": "Banner",
        "format": "jpg", "max_size_kb": 150,
    },
    # Responsive Display Ads
    "responsive_landscape": {
        "width": 1200, "height": 628, "name": "Responsive Landscape",
        "format": "jpg", "max_size_kb": 5120,
    },
    "responsive_square": {
        "width": 1200, "height": 1200, "name": "Responsive Square",
        "format": "jpg", "max_size_kb": 5120,
    },
}

# GDN limits: images 150KB, HTML5 600KB ZIP, GIF ≤30s ≤5FPS
GOOGLE_RULES = {
    "image_max_kb": 150,
    "html5_zip_max_kb": 600,
    "gif_max_duration": 30,
    "gif_max_fps": 5,
    "animation_max_duration": 30,
}

# ──────────────────────────────────────────────────────────────
# LINKEDIN
# ──────────────────────────────────────────────────────────────
LINKEDIN_SIZES = {
    "single_landscape": {
        "width": 1200, "height": 628, "aspect_ratio": "1.91:1",
        "format": "jpg", "max_size_mb": 5,
        "placement": "Single Image (paysage)",
    },
    "single_square": {
        "width": 1200, "height": 1200, "aspect_ratio": "1:1",
        "format": "jpg", "max_size_mb": 5,
        "placement": "Single Image (carré)",
    },
    "single_vertical": {
        "width": 720, "height": 900, "aspect_ratio": "4:5",
        "format": "jpg", "max_size_mb": 5,
        "placement": "Single Image (vertical, mobile only)",
    },
    "carousel": {
        "width": 1080, "height": 1080, "aspect_ratio": "1:1",
        "format": "jpg", "max_size_mb": 10,
        "placement": "Carousel",
    },
    "video": {
        "width": 1920, "height": 1080, "aspect_ratio": "16:9",
        "format": "mp4", "max_size_mb": 200, "max_duration": 1800,
        "placement": "Vidéo",
    },
    "text_ads": {
        "width": 100, "height": 100, "aspect_ratio": "1:1",
        "format": "jpg", "max_size_mb": 2,
        "placement": "Text Ads",
    },
    "message_banner": {
        "width": 300, "height": 250, "aspect_ratio": "1.2:1",
        "format": "jpg", "max_size_mb": 2,
        "placement": "Message Ads banner",
    },
    "ctv": {
        "width": 1920, "height": 1080, "aspect_ratio": "16:9",
        "format": "mp4", "max_size_mb": 500, "max_duration": 30,
        "placement": "CTV Ads",
    },
}

# ──────────────────────────────────────────────────────────────
# CROSS-PLATFORM ESSENTIALS — the 5 sizes to always produce
# ──────────────────────────────────────────────────────────────
ESSENTIAL_SIZES = {
    "square_1080": {"width": 1080, "height": 1080, "aspect_ratio": "1:1",
                     "use": "Meta Feed + LinkedIn + Google Responsive"},
    "portrait_1080x1350": {"width": 1080, "height": 1350, "aspect_ratio": "4:5",
                            "use": "Meta Feed mobile 4:5"},
    "story_1080x1920": {"width": 1080, "height": 1920, "aspect_ratio": "9:16",
                         "use": "Stories/Reels"},
    "landscape_1200x628": {"width": 1200, "height": 628, "aspect_ratio": "1.91:1",
                            "use": "LinkedIn + Google Responsive paysage"},
    "gdn_300x250": {"width": 300, "height": 250, "aspect_ratio": "6:5",
                     "use": "GDN + LinkedIn banner"},
}

# ──────────────────────────────────────────────────────────────
# CLICKTAG PATTERNS per platform
# ──────────────────────────────────────────────────────────────
CLICKTAG_PATTERNS = {
    "google_ads": {
        "variable": "clickTag",
        "case": "lowercase t",
        "implementation": 'var clickTag = "URL";',
        "placement": "<head>",
    },
    "dv360": {
        "variable": "clickTag",
        "implementation": 'var clickTag = "URL";',
    },
    "campaign_manager_360": {
        "variable": "clickTag",
        "implementation": 'var clickTag = "URL";',
    },
    "adform": {
        "variable": "clickTAG",
        "case": "uppercase TAG",
        "implementation": "dhtml.getVar('clickTAG', 'URL')",
    },
    "sizmek": {
        "variable": "via adkit",
        "implementation": "EB.clickthrough()",
    },
}

# ──────────────────────────────────────────────────────────────
# FILE SIZE LIMITS per platform (for HTML5 ads)
# ──────────────────────────────────────────────────────────────
PLATFORM_LIMITS = {
    "google_gdn": {"zip_max_kb": 150, "animation_max_s": 30, "notes": "No external scripts, no video"},
    "google_html5": {"zip_max_kb": 600, "animation_max_s": 30, "notes": "Same restrictions"},
    "dv360": {"zip_max_kb": 300, "animation_max_s": 30, "notes": "CDN Google authorized, polite loading"},
    "campaign_manager": {"zip_max_mb": 9.5, "animation_max_s": 30, "notes": "ZIP or ADZ"},
    "iab_standard": {"initial_kb": 50, "subload_kb": 100, "animation_max_s": 30, "notes": "LEAN principles"},
}


# ──────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────

def get_platform_sizes(platform: str) -> dict:
    """Get all ad sizes for a platform."""
    registry = {
        "meta": META_SIZES,
        "google": GOOGLE_SIZES,
        "linkedin": LINKEDIN_SIZES,
    }
    return registry.get(platform, {})


def get_platform_image_sizes(platform: str) -> dict:
    """Get only image (non-video) sizes for a platform."""
    sizes = get_platform_sizes(platform)
    return {
        k: v for k, v in sizes.items()
        if v.get("format", "jpg") in ("jpg", "png", "jpeg")
    }


def get_essential_sizes() -> dict:
    """Get the 5 cross-platform essential sizes."""
    return ESSENTIAL_SIZES


def get_clicktag(platform: str) -> dict:
    """Get clicktag pattern for a platform."""
    return CLICKTAG_PATTERNS.get(platform, CLICKTAG_PATTERNS["google_ads"])


def get_platform_limit(platform: str) -> dict:
    """Get file size limits for a platform."""
    return PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["google_gdn"])
