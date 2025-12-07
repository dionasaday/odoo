/** @odoo-module **/

/**
 * Logging utility for production-ready error handling
 * Only logs in development mode, silent in production
 */
const isDevelopment = typeof window !== 'undefined' && window.location.hostname === 'localhost';

export const logger = {
    error: (message, error) => {
        if (isDevelopment) {
            console.error(message, error);
        }
        // In production: errors are silently handled, could integrate with error tracking service
    },
    warn: (message, data) => {
        if (isDevelopment) {
            console.warn(message, data);
        }
    },
    log: (message, data) => {
        if (isDevelopment) {
            console.log(message, data);
        }
    },
    debug: (message, data) => {
        if (isDevelopment) {
            console.debug(message, data);
        }
    }
};

