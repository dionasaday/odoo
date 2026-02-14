/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useState } from "@odoo/owl";
import { CharField, charField } from "@web/views/fields/char/char_field";

export class HelpdeskPasswordToggleField extends CharField {
    setup() {
        super.setup();
        this.state = useState({ show: false });
    }

    get toggleTitle() {
        return this.state.show ? _t("Hide value") : _t("Show value");
    }

    togglePassword(ev) {
        ev.preventDefault();
        this.state.show = !this.state.show;
        if (this.input?.el) {
            this.input.el.focus();
        }
    }
}

HelpdeskPasswordToggleField.template = "helpdesk_mgmt.HelpdeskPasswordToggleField";

registry.category("fields").add("helpdesk_password_toggle", {
    component: HelpdeskPasswordToggleField,
    displayName: _t("Password (toggle)"),
    supportedTypes: ["char", "text"],
    extractProps: (fieldInfo) => {
        const props = charField.extractProps(fieldInfo);
        props.isPassword = true;
        return props;
    },
});
