/** @odoo-module */
import { NavBar } from "@web/webclient/navbar/navbar";
import { registry } from "@web/core/registry";
import { fuzzyLookup } from "@web/core/utils/search";
import { computeAppsAndMenuItems } from "@web/webclient/menus/menu_helpers";
import { useService } from "@web/core/utils/hooks";
import { onMounted, useRef, useState} from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(NavBar.prototype, {
    // To modify the Navbar properties and functions.
    setup() {
        super.setup()
        this._search_def = this.createDeferred();
        this.search_container = useRef("search-container");
        this.search_input = useRef("search-input");
        this.search_result = useRef("search-results");
        this.menuService = useService("menu");
        this.app_menu = useRef("app-menu");
        this.sidebar_panel = useRef("sidebar_panel");
        this.app_components = useRef("app_components");
        this.state = useState({...this.state, menus: [], searchQuery: ""})
        let { apps, menuItems } = computeAppsAndMenuItems(this.menuService.getMenuAsTree("root"));
        this._apps = apps;
        this._searchableMenus = menuItems;
        this.fetch_data()
        onMounted(() => {
            this.setClass()
            this.toggleFullscreenBackground()
            // Watch for fullscreen menu changes
            const observer = new MutationObserver(() => {
                this.toggleFullscreenBackground()
            })
            observer.observe(document.body, {
                childList: true,
                subtree: true
            })
            
            // Close app menu when clicking ActivityMenu items
            this.setupActivityMenuClickHandler()
        })
    },
    createDeferred() {
    let deferred = {};

    deferred.promise = new Promise((resolve, reject) => {
        deferred.resolve = resolve;
        deferred.reject = reject;
    });

    return deferred;
},
    async fetch_data() {
        // To fetch colors from database.
        this.orm = useService("orm")
        var result = await this.orm.call("res.config.settings", "config_color_settings", [0])
        if (result.primary_accent !== false){
            document.documentElement.style.setProperty("--primary-accent",result.primary_accent)
        }
        if (result.appbar_color !== false){
            document.documentElement.style.setProperty("--app-bar-accent",result.appbar_color)
        }
        if (result.primary_hover !== false){
            document.documentElement.style.setProperty("--primary-hover",result.primary_hover)
        }
        if (result.full_bg_img !== false) {
            var imageUrl = 'url(data:image/png;base64,' + result.full_bg_img + ')';
            // Set CSS variable for body::before background
            document.documentElement.style.setProperty("--full-screen-bg", imageUrl);
            // Also set for app_components elements (backward compatibility)
            var appComponentsDivs = document.getElementsByClassName('app_components');
            for (var i = 0; i < appComponentsDivs.length; i++) {
                appComponentsDivs[i].style.backgroundImage = imageUrl;
            }
        } else {
            // Reset to default if no custom image
            document.documentElement.style.setProperty("--full-screen-bg", "url(/jazzy_backend_theme/static/src/img/background.jpg)");
        }
        if (result.appbar_text !== false){
            document.documentElement.style.setProperty("--app-menu-font-color",result.appbar_text)
        }
        if (result.secondary_hover !== false){
            document.documentElement.style.setProperty("--secondary-hover",result.secondary_hover)
        }
        if (result.kanban_bg_color !== false) {
            document.documentElement.style.setProperty("--kanban-bg-color", result.kanban_bg_color)
        }
    },
    setClass() {
        // Set variable for html elements.
        this.$search_container = this.search_container;
        this.$search_input = this.search_input;
        this.$search_results = this.search_result;
        this.$app_menu = this.app_menu;
    },
    _searchMenusSchedule() {
        this.$search_results.el.classList.remove("o_hidden");
        this.$app_menu.el.classList.add("o_hidden");
        this._search_def = this.createDeferred();
        this._searchMenus();
    },
    _searchMenus() {
        // App menu search function
        var query = this.state.searchQuery;
        if (query === "") {
            this.$search_container.el.classList.remove("has-results");
            this.$search_results.el.classList.add("o_hidden")
            this.$app_menu.el.classList.remove("o_hidden");
            return;
        }
        var results = [];
        fuzzyLookup(query, this._apps, (menu) => menu.label)
        .forEach((menu) => {
            results.push({
                category: "apps",
                name: menu.label,
                actionID: menu.actionID,
                id: menu.id,
                webIconData: menu.webIconData,
            });
        });
        fuzzyLookup(query, this._searchableMenus, (menu) =>
            (menu.parents + " / " + menu.label).split("/").reverse().join("/")
        ).forEach((menu) => {
            results.push({
                category: "menu_items",
                name: menu.parents + " / " + menu.label,
                actionID: menu.actionID,
                id: menu.id,
            });
        });
        this.state.menus = results
    },
    get menus() {
        return this.state.menus
    },
    handleClick(menu) {
        this.app_components.el.nextSibling.style.display = "block";
        this.app_components.el.style.display = "none";
        this.app_components.el.style.opacity = "0";
        // Immediately update background visibility and remove class
        document.body.classList.remove('has-app-components');
        this.toggleFullscreenBackground()

        this.sidebar_panel.el.style.display = "block";
        this.app_menu.el.classList.remove('o_hidden');

        let children = this.app_components.el.parentElement.children;
        let oNavbar = null;

        for (let i = 0; i < children.length; i++) {
            if (children[i].classList.contains('o_navbar')) {
                oNavbar = children[i];
                break;
            }
        }

        let navChild = oNavbar.children[0].children;
        for (let i = 0; i < navChild.length; i++) {
            if (navChild[i].classList.contains('o_menu_brand')) {
                navChild[i].classList.remove('d-none');
                navChild[i].classList.add('d-block');
            }
            if (navChild[i].classList.contains('o_menu_sections')) {
                navChild[i].classList.remove('d-none');
                navChild[i].classList.add('d-block');
            }
        }
        if (menu) {
            this.menuService.selectMenu(menu.id);
        }
    },
    OnClickMainMenu() {
        // To show search screen
        if (this.app_components.el.style.display === "" || this.app_components.el.style.display === "none" ) {
            let children = this.app_components.el.parentElement.children;
            let oNavbar = null;
            for (let i = 0; i < children.length; i++) {
                if (children[i].classList.contains('o_navbar')) {
                    oNavbar = children[i];
                    break;
                }
            }
            let navChild = oNavbar.children[0].children
            for (let i = 0; i < navChild.length; i++) {
                if (navChild[i].classList.contains('o_menu_brand')) {
                    navChild[i].classList.add('d-none')
                }
                if (navChild[i].classList.contains('o_menu_sections')) {
                    navChild[i].classList.add('d-none')
                }
            }
            this.app_components.el.style.transition = "opacity 0.25s"
            this.app_components.el.style.opacity="1"
            this.app_components.el.style.display = "block"
            this.app_components.el.nextSibling.style.display = "none"
            this.sidebar_panel.el.style.display = "none"
            // Update background visibility
            this.toggleFullscreenBackground()
        } else {
            this.app_components.el.style.transition = "opacity 0.05s";
            this.app_components.el.style.opacity = "0";
            setTimeout(() => {
                this.app_components.el.style.display = "none";
                // Update background visibility after hiding
                this.toggleFullscreenBackground()
            }, 50);
            this.app_components.el.nextSibling.style.display = "block"
            this.sidebar_panel.el.style.display = "block"
            let children = this.app_components.el.parentElement.children;
            let oNavbar = null;
            for (let i = 0; i < children.length; i++) {
                if (children[i].classList.contains('o_navbar')) {
                    oNavbar = children[i];
                    break;
                }
            }
            let navChild = oNavbar.children[0].children
            for (let i = 0; i < navChild.length; i++) {
                if (navChild[i].classList.contains('o_menu_brand')) {
                    navChild[i].classList.remove('d-none')
                }
                if (navChild[i].classList.contains('o_menu_sections')) {
                    navChild[i].classList.remove('d-none')
                }
            }
        }
    },
    onNavBarDropdownItemSelection(app) {
        // To go to app menu - hide app_components immediately
        this.app_components.el.style.display = "none";
        this.app_components.el.style.opacity = "0";
        this.app_components.el.nextSibling.style.display = "block"
        this.sidebar_panel.el.style.display = "block"
        // Immediately update background visibility and remove class
        document.body.classList.remove('has-app-components');
        this.toggleFullscreenBackground()
        let children = this.app_components.el.parentElement.children;
            let oNavbar = null;
            for (let i = 0; i < children.length; i++) {
                if (children[i].classList.contains('o_navbar')) {
                    oNavbar = children[i];
                    break;
                }
            }
            let navChild = oNavbar.children[0].children
            for (let i = 0; i < navChild.length; i++) {
                if (navChild[i].classList.contains('o_menu_brand')) {
                    navChild[i].classList.add('d-flex')
                    navChild[i].classList.remove('d-none')
                }
                if (navChild[i].classList.contains('o_menu_sections')) {
                    navChild[i].classList.add('d-flex')
                    navChild[i].classList.remove('d-none')
                }
            }
        if (app) {
            this.menuService.selectMenu(app);
        }
    },
    refreshNavBar() {
        // Find the navbar element
        let children = this.app_components.el.parentElement.children;
        let oNavbar = null;

        // Locate the navbar component
        for (let i = 0; i < children.length; i++) {
            if (children[i].classList.contains('o_navbar')) {
                oNavbar = children[i];
                break;
            }
        }

        if (oNavbar) {
            let navChild = oNavbar.children[0].children;
            // Ensure the navbar sections are displayed correctly
            for (let i = 0; i < navChild.length; i++) {
                if (navChild[i].classList.contains('o_menu_brand')) {
                    navChild[i].classList.remove('d-none');
                    navChild[i].classList.add('d-block');
                }
                if (navChild[i].classList.contains('o_menu_sections')) {
                    navChild[i].classList.remove('d-none');
                    navChild[i].classList.add('d-block');
                }
            }
        }
    },
    /**
     * Safely check if webIcon is a string and includes the given extension
     * @param {string|undefined|null} webIcon - The webIcon value to check
     * @param {string} extension - The extension to check for (e.g., '.png', '.svg')
     * @returns {boolean} - True if webIcon is a string and includes the extension
     */
    hasWebIconExtension(webIcon, extension) {
        return webIcon && typeof webIcon === 'string' && webIcon.includes(extension);
    },
    toggleFullscreenBackground() {
        // Toggle class on body based on app_components visibility
        const appComponents = document.querySelector('.app_components')
        if (appComponents) {
            const style = window.getComputedStyle(appComponents)
            // Check if app_components is visible (not display: none)
            if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                document.body.classList.add('has-app-components')
            } else {
                document.body.classList.remove('has-app-components')
            }
        } else {
            document.body.classList.remove('has-app-components')
        }
    },
    setupActivityMenuClickHandler() {
        // Close app menu when clicking on ActivityMenu items
        const closeAppMenuOnActivityClick = (event) => {
            // Check if click is on ActivityMenu dropdown item
            const activityMenu = event.target.closest('.o_ActivityMenu')
            if (activityMenu) {
                const activityItem = event.target.closest('.o-mail-ActivityGroup, .o-mail-ActivityGroup a, .o_activity_summary, .o_activity_summary_cell, [class*="activity"]')
                if (activityItem && this.app_components && this.app_components.el) {
                    const appComponentsStyle = window.getComputedStyle(this.app_components.el)
                    // If app menu is open, close it immediately
                    if (appComponentsStyle.display !== 'none' && appComponentsStyle.visibility !== 'hidden') {
                        this.app_components.el.style.display = 'none'
                        this.app_components.el.style.opacity = '0'
                        if (this.app_components.el.nextSibling) {
                            this.app_components.el.nextSibling.style.display = 'block'
                        }
                        if (this.sidebar_panel && this.sidebar_panel.el) {
                            this.sidebar_panel.el.style.display = 'block'
                        }
                        document.body.classList.remove('has-app-components')
                        this.toggleFullscreenBackground()
                    }
                }
            }
        }
        
        // Use event delegation on document body with capture phase
        document.body.addEventListener('click', closeAppMenuOnActivityClick, true)
        
        // Watch for URL changes using popstate and pushState
        let lastUrl = window.location.href
        
        // Override pushState to detect programmatic navigation
        const originalPushState = history.pushState
        history.pushState = (...args) => {
            originalPushState.apply(history, args)
            this.closeAppMenuIfOpen()
        }
        
        // Listen to popstate (back/forward button)
        window.addEventListener('popstate', () => {
            this.closeAppMenuIfOpen()
        })
        
        // Fallback: Check URL periodically
        setInterval(() => {
            const currentUrl = window.location.href
            if (currentUrl !== lastUrl) {
                lastUrl = currentUrl
                this.closeAppMenuIfOpen()
            }
        }, 200)
    },
    closeAppMenuIfOpen() {
        // Close app menu if it's open
        if (this.app_components && this.app_components.el) {
            const appComponentsStyle = window.getComputedStyle(this.app_components.el)
            if (appComponentsStyle.display !== 'none' && appComponentsStyle.visibility !== 'hidden') {
                this.app_components.el.style.display = 'none'
                this.app_components.el.style.opacity = '0'
                if (this.app_components.el.nextSibling) {
                    this.app_components.el.nextSibling.style.display = 'block'
                }
                if (this.sidebar_panel && this.sidebar_panel.el) {
                    this.sidebar_panel.el.style.display = 'block'
                }
                document.body.classList.remove('has-app-components')
                this.toggleFullscreenBackground()
            }
        }
    }
})
