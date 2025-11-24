/** @odoo-module **/

const TARGET_SELECTOR =
    '.o_form_view .o_field_widget[name="type"] input[type="radio"][value="product"]';

function hideStorableProduct() {
    const radios = document.querySelectorAll(TARGET_SELECTOR);
    radios.forEach((radio) => {
        const container = radio.closest('.o_radio_item') || radio.parentElement;
        if (container && container.style.display !== 'none') {
            container.style.display = 'none';
        }
    });
}

function initMutationObserver() {
    hideStorableProduct();
    const observer = new MutationObserver((mutationsList) => {
        let shouldRun = false;
        for (const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                shouldRun = true;
                break;
            }
        }
        if (shouldRun) {
            hideStorableProduct();
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

document.addEventListener('DOMContentLoaded', () => {
    hideStorableProduct();
    initMutationObserver();
});

// In case assets are loaded after DOM ready (during dynamic JS loading)
if (document.readyState !== 'loading') {
    hideStorableProduct();
    initMutationObserver();
}


