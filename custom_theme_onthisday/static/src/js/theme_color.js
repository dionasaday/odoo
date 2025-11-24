/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/**
 * Apply theme colors from company settings to CSS variables
 */
async function loadAndApplyThemeColors() {
    try {
        // Wait a bit to ensure Odoo is ready
        await new Promise(resolve => setTimeout(resolve, 200));
        
        // Check if rpc is available
        if (typeof rpc !== 'function') {
            return;
        }
        
        // Get theme colors from server
        const colors = await rpc("/custom_theme/get_colors", {}).catch((error) => {
            console.warn("Theme colors RPC error:", error);
            return null;
        });
        
        // Validate that colors is an object
        if (colors && typeof colors === 'object' && !Array.isArray(colors)) {
            const root = document.documentElement;

            // Apply primary color with !important
            if (colors.theme_primary_color) {
                root.style.setProperty("--o-brand-primary", colors.theme_primary_color, "important");
                root.style.setProperty("--NavBar-entry-backgroundColor", colors.theme_primary_color, "important");
                
                // Apply directly to navbar elements
                const navbar = document.querySelector('.o_main_navbar');
                if (navbar) {
                    navbar.style.setProperty("background-color", colors.theme_primary_color, "important");
                }
                
                // Apply to all menu sections
                document.querySelectorAll('.o_menu_sections > .o_menu_section').forEach(el => {
                    el.style.setProperty("background-color", colors.theme_primary_color, "important");
                });
            }

            // Apply secondary color
            if (colors.theme_secondary_color) {
                root.style.setProperty("--o-brand-secondary", colors.theme_secondary_color, "important");
                root.style.setProperty("--NavBar-entry-active-backgroundColor", colors.theme_secondary_color, "important");
            }

            // Apply text color
            if (colors.theme_text_color) {
                root.style.setProperty("--o-brand-optional", colors.theme_text_color, "important");
            }
        }
    } catch (error) {
        // Silently fail if colors can't be loaded
        console.warn("Theme colors: Failed to load", error);
    }
}

// Store last applied colors to avoid unnecessary updates
let lastColors = null;

// Enhanced function to apply colors
async function applyThemeColors() {
    try {
        // Check if rpc is available (Odoo might not be fully loaded)
        if (typeof rpc !== 'function') {
            return;
        }
        
        const colors = await rpc("/custom_theme/get_colors", {}).catch((error) => {
            // Silently fail if RPC error occurs
            console.warn("Theme colors RPC error:", error);
            return null;
        });
        
        // Validate that colors is an object
        if (!colors || typeof colors !== 'object' || Array.isArray(colors)) {
            return;
        }
        
        // Check if colors have changed
        const colorsKey = JSON.stringify(colors);
        if (lastColors === colorsKey) return;
        lastColors = colorsKey;
    
    const root = document.documentElement;
    
    // Apply colors with !important
    if (colors.theme_primary_color) {
        root.style.setProperty("--o-brand-primary", colors.theme_primary_color, "important");
        root.style.setProperty("--NavBar-entry-backgroundColor", colors.theme_primary_color, "important");
        
        // Force apply to navbar
        requestAnimationFrame(() => {
            const navbar = document.querySelector('.o_main_navbar');
            if (navbar) {
                navbar.style.cssText += `background-color: ${colors.theme_primary_color} !important;`;
            }
            
            // Apply to menu items
            document.querySelectorAll('.o_menu_sections .o_menu_section').forEach(el => {
                el.style.cssText += `background-color: ${colors.theme_primary_color} !important;`;
            });
        });
    }
    
    if (colors.theme_secondary_color) {
        root.style.setProperty("--o-brand-secondary", colors.theme_secondary_color, "important");
        root.style.setProperty("--NavBar-entry-active-backgroundColor", colors.theme_secondary_color, "important");
    }
    
    if (colors.theme_text_color) {
        root.style.setProperty("--o-brand-optional", colors.theme_text_color, "important");
    }
    } catch (error) {
        // Silently fail if any error occurs during color application
        console.warn("Theme colors application error:", error);
    }
}

// Apply immediately
applyThemeColors();

// Apply on page load
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        setTimeout(applyThemeColors, 500);
        setTimeout(applyThemeColors, 1500);
    });
} else {
    setTimeout(applyThemeColors, 500);
    setTimeout(applyThemeColors, 1500);
}

// Apply on navigation (Odoo SPA navigation)
const originalPushState = history.pushState;
history.pushState = function() {
    originalPushState.apply(history, arguments);
    setTimeout(applyThemeColors, 300);
};

const originalReplaceState = history.replaceState;
history.replaceState = function() {
    originalReplaceState.apply(history, arguments);
    setTimeout(applyThemeColors, 300);
};

window.addEventListener("popstate", () => {
    setTimeout(applyThemeColors, 300);
});

// Listen for focus events (when user returns to tab)
window.addEventListener("focus", () => {
    setTimeout(applyThemeColors, 500);
});

// Watch for form save button clicks
document.addEventListener("click", (e) => {
    const target = e.target;
    if (target && (
        target.classList.contains("o_form_button_save") ||
        target.closest(".o_form_button_save") ||
        (target.type === "submit" && target.closest("form"))
    )) {
        // Form is being saved, reload colors after a delay
        setTimeout(() => {
            lastColors = null; // Force reload
            applyThemeColors();
            setTimeout(applyThemeColors, 1000);
            setTimeout(applyThemeColors, 2000);
        }, 500);
    }
}, true);

// Reload colors periodically (every 3 seconds) as fallback
// Wrap in try-catch to prevent errors from breaking the interval
setInterval(() => {
    try {
        applyThemeColors();
    } catch (error) {
        console.warn("Theme colors interval error:", error);
    }
}, 3000);

