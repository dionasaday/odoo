/** @odoo-module **/

/**
 * Global RPC error handler to catch JSON.parse errors from failed requests
 * This handles cases where routes return HTML error pages instead of JSON
 * 
 * IMPORTANT: This must load early to intercept fetch/XHR calls before they're used
 * 
 * Based on Odoo 19 Error Handling best practices:
 * - https://www.odoo.com/documentation/19.0/developer/reference/web_framework/error_handling.html
 * - Intercepts errors before they reach Odoo's crash_manager
 * - Handles non-JSON responses gracefully
 */
(function() {
    'use strict';
    
    // Register error handler IMMEDIATELY, before any other code runs
    // This ensures we catch errors as early as possible
    
    // Global error handler for unhandled promise rejections (JSON.parse errors)
    // Register FIRST before overriding fetch/XHR
    // Use capture phase and handle early to prevent "Uncaught (in promise)" errors
    window.addEventListener('unhandledrejection', function(event) {
        const error = event.reason;
        
        // Check if it's a JSON.parse error
        if (error && (
            (error.message && (error.message.includes('JSON.parse') || error.message.includes('unexpected character'))) ||
            (error.name === 'SyntaxError' && error.message && (error.message.includes('JSON') || error.message.includes('unexpected character')))
        )) {
            // Check if this is related to dashboard
            const isDashboardError = error.message && (
                error.message.includes('dashboard') || 
                error.message.includes('dashboards') ||
                (event.promise && typeof event.promise === 'object' && event.promise._url && 
                 (event.promise._url.includes('dashboard') || event.promise._url.includes('dashboards')))
            );
            
            if (isDashboardError) {
                console.error('Caught JSON.parse error in dashboard request:', error);
                console.error('This usually means a dashboard route returned HTML or empty response instead of JSON');
            } else {
                console.warn('Caught JSON.parse error, likely from non-JSON response:', error);
                console.warn('This usually means a route returned HTML or empty response instead of JSON');
            }
            
            // CRITICAL: Prevent default error handling FIRST
            // This prevents the "Uncaught (in promise)" error from showing
            event.preventDefault();
            event.stopImmediatePropagation();
            event.stopPropagation();
            
            // Try to handle the promise to prevent further rejections
            if (event.promise) {
                // Add a catch handler to the promise to consume the rejection
                Promise.resolve(event.promise).catch(() => {
                    // Silently consume the error - already logged above
                });
            }
            
            // Mark as handled
            return false;
        }
    }, true); // Use capture phase to catch early
    
    // Also add a handler for error events that might bubble up
    window.addEventListener('error', function(event) {
        const error = event.error;
        
        // Check if it's a JSON.parse error
        if (error && error.name === 'SyntaxError' && error.message && 
            (error.message.includes('JSON.parse') || error.message.includes('unexpected character'))) {
            console.warn('Caught JSON.parse error in error event:', error);
            
            // Prevent default error handling
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            
            return false;
        }
    }, true); // Use capture phase
    
    // Store original fetch if available
    const originalFetch = window.fetch;
    
    // Override fetch to handle non-JSON responses
    if (originalFetch) {
        window.fetch = async function(...args) {
            try {
                const response = await originalFetch.apply(this, args);
                const url = args[0] || '';
                
                // Store original methods
                const originalJson = response.json.bind(response);
                const originalText = response.text.bind(response);
                let responseTextCache = null;
                let responseTextPromise = null;
                
                // Cache the text response to avoid multiple reads
                const getCachedText = async function() {
                    if (responseTextCache !== null) {
                        return responseTextCache;
                    }
                    if (responseTextPromise) {
                        return responseTextPromise;
                    }
                    responseTextPromise = originalText().then(text => {
                        responseTextCache = text;
                        return text;
                    });
                    return responseTextPromise;
                };
                
                // Override response.json() to handle HTML responses and empty responses
                // IMPORTANT: This must be done BEFORE any code calls .json()
                // Wrap in Promise.resolve to ensure errors are caught
                response.json = function() {
                    // Return a promise that handles all errors gracefully
                    return Promise.resolve().then(async () => {
                        try {
                            // First, check if response body is already consumed
                            const text = await getCachedText();
                            
                            // Check if text is empty or only whitespace
                            const trimmedText = text ? text.trim() : '';
                            if (!text || trimmedText === '') {
                                // Status 0 usually means request was cancelled or network error
                                // This is normal when navigating away or page unloads
                                // Only log warning for non-zero status codes
                                if (response.status === 0) {
                                    // Request was cancelled - this is normal, don't log warning
                                    // Return empty object silently
                                    return {};
                                }
                                
                                // For other status codes, log warning only for important routes
                                if (url.includes('dashboard') || url.includes('dashboards')) {
                                    console.warn(`Route ${url} returned empty response. Status: ${response.status}`);
                                    return {
                                        error: 'Dashboard Error',
                                        message: 'Dashboard data is empty or unavailable',
                                        status: response.status,
                                        dashboard_id: url.match(/dashboard_id=(\d+)/)?.[1] || null
                                    };
                                }
                                
                                // For non-dashboard routes with non-zero status, only log if status >= 400
                                if (response.status >= 400) {
                                    console.warn(`Route ${url} returned empty response. Status: ${response.status}`);
                                }
                                
                                return {}; // Return empty object
                            }
                            
                            // Check if text looks like HTML (starts with < or contains HTML tags)
                            if (trimmedText.startsWith('<') || /^[\s]*<[^>]+>/.test(trimmedText)) {
                                console.warn(`Route ${url} returned HTML instead of JSON. Status: ${response.status}`);
                                
                                // For dashboard routes, provide more specific error
                                if (url.includes('dashboard') || url.includes('dashboards')) {
                                    return {
                                        error: 'Dashboard Error',
                                        message: 'Dashboard route returned HTML instead of JSON. This may indicate a server error or authentication issue.',
                                        status: response.status,
                                        dashboard_id: url.match(/dashboard_id=(\d+)/)?.[1] || null,
                                        html_response: true
                                    };
                                }
                                
                                // Return appropriate JSON based on status
                                if (response.status >= 400) {
                                    return {
                                        error: 'Server Error',
                                        message: `Request failed with status ${response.status}`,
                                        status: response.status
                                    };
                                } else {
                                    return {}; // Empty object for successful but HTML responses
                                }
                            }
                            
                            // Try to parse as JSON
                            try {
                                return JSON.parse(text);
                            } catch (parseError) {
                                // If JSON.parse fails, check if it's a dashboard route
                                if (url.includes('dashboard') || url.includes('dashboards')) {
                                    console.error(`Dashboard route ${url} returned invalid JSON. Status: ${response.status}`);
                                    console.error(`Parse error: ${parseError.message}`);
                                    console.error(`Response preview: ${trimmedText.substring(0, 200)}`);
                                    
                                    return {
                                        error: 'Dashboard Parse Error',
                                        message: `Failed to parse dashboard data: ${parseError.message}`,
                                        status: response.status,
                                        dashboard_id: url.match(/dashboard_id=(\d+)/)?.[1] || null,
                                        parse_error: parseError.message
                                    };
                                }
                                
                                // For non-dashboard routes, return empty object
                                console.warn(`Route ${url} returned non-JSON response. Status: ${response.status}, Content: ${trimmedText.substring(0, 100)}`);
                                console.warn(`Parse error: ${parseError.message}`);
                                return {};
                            }
                        } catch (textError) {
                            // If we can't read text, return appropriate error
                            console.warn(`Could not read response text: ${textError}`);
                            
                            // For dashboard routes, return specific error
                            if (url.includes('dashboard') || url.includes('dashboards')) {
                                return {
                                    error: 'Dashboard Read Error',
                                    message: `Could not read dashboard response: ${textError.message || textError}`,
                                    status: response.status,
                                    dashboard_id: url.match(/dashboard_id=(\d+)/)?.[1] || null
                                };
                            }
                            
                            return {};
                        }
                    }).catch((error) => {
                        // Catch any errors in the promise chain
                        console.warn(`Error in response.json() for ${url}:`, error);
                        
                        // For dashboard routes, return specific error
                        if (url.includes('dashboard') || url.includes('dashboards')) {
                            return {
                                error: 'Dashboard Error',
                                message: `Unexpected error loading dashboard: ${error.message || error}`,
                                status: response.status || 500,
                                dashboard_id: url.match(/dashboard_id=(\d+)/)?.[1] || null
                            };
                        }
                        
                        return {};
                    });
                };
                
                // Also override text() to cache the result
                response.text = async function() {
                    return await getCachedText();
                };
                
                // Pre-check response for HTML content if it's an error
                if (!response.ok) {
                    const contentType = response.headers.get('content-type') || '';
                    const isJSON = contentType.includes('application/json');
                    
                    if (!isJSON) {
                        // Pre-read text to check if it's HTML
                        getCachedText().then(text => {
                            if (text && text.trim().startsWith('<')) {
                                console.warn(`Route ${url} returned HTML error page. Status: ${response.status}`);
                            }
                        }).catch(() => {
                            // Ignore errors in pre-check
                        });
                    }
                }
                
                return response;
            } catch (error) {
                // If fetch itself fails, rethrow
                throw error;
            }
        };
    }
    
    // Also patch XMLHttpRequest for older code
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;
    
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this._url = url;
        return originalXHROpen.apply(this, [method, url, ...rest]);
    };
    
    XMLHttpRequest.prototype.send = function(...args) {
        const xhr = this;
        const originalOnReadyStateChange = xhr.onreadystatechange;
        const originalOnLoad = xhr.onload;
        const originalOnError = xhr.onerror;
        
        // Helper function to check and convert HTML to JSON
        const checkAndConvertResponse = function() {
            if (xhr.readyState === 4) {
                // Check if response is HTML instead of JSON
                const contentType = xhr.getResponseHeader('content-type') || '';
                const isJSON = contentType.includes('application/json');
                const responseText = xhr.responseText || '';
                
                // Check if response is empty or only whitespace
                const trimmedResponse = responseText ? responseText.trim() : '';
                const isDashboardRoute = xhr._url && (xhr._url.includes('dashboard') || xhr._url.includes('dashboards'));
                const dashboardId = isDashboardRoute ? (xhr._url.match(/dashboard_id=(\d+)/)?.[1] || null) : null;
                
                if (!responseText || trimmedResponse === '') {
                    // Status 0 usually means request was cancelled or network error
                    // This is normal when navigating away or page unloads
                    // Only log warning for non-zero status codes
                    if (xhr.status === 0) {
                        // Request was cancelled - this is normal, don't log warning
                        // Return empty object silently
                        try {
                            const emptyResponse = JSON.stringify({});
                            Object.defineProperty(xhr, 'responseText', {
                                value: emptyResponse,
                                writable: false,
                                configurable: true
                            });
                            Object.defineProperty(xhr, 'response', {
                                value: emptyResponse,
                                writable: false,
                                configurable: true
                            });
                        } catch (e) {
                            // Ignore errors in conversion
                        }
                        return;
                    }
                    
                    // For non-zero status codes, log warning only for important routes
                    if (isDashboardRoute) {
                        console.warn(`XHR to ${xhr._url} returned empty response. Status: ${xhr.status}`);
                    } else if (xhr.status >= 400) {
                        console.warn(`XHR to ${xhr._url} returned empty response. Status: ${xhr.status}`);
                    }
                    
                    // Create appropriate JSON response
                    try {
                        let emptyResponse;
                        if (isDashboardRoute) {
                            emptyResponse = JSON.stringify({
                                error: 'Dashboard Error',
                                message: 'Dashboard data is empty or unavailable',
                                status: xhr.status,
                                dashboard_id: dashboardId
                            });
                        } else {
                            emptyResponse = JSON.stringify({});
                        }
                        
                        Object.defineProperty(xhr, 'responseText', {
                            value: emptyResponse,
                            writable: false,
                            configurable: true
                        });
                        Object.defineProperty(xhr, 'response', {
                            value: emptyResponse,
                            writable: false,
                            configurable: true
                        });
                    } catch (e) {
                        console.error('Error converting empty response to JSON:', e);
                    }
                    return;
                }
                
                // Check if response looks like HTML (starts with < or contains HTML tags)
                if (trimmedResponse.startsWith('<') || /^[\s]*<[^>]+>/.test(trimmedResponse)) {
                    console.warn(`XHR to ${xhr._url} returned HTML instead of JSON. Status: ${xhr.status}`);
                    
                    // Create a JSON error response
                    try {
                        let errorResponse;
                        if (isDashboardRoute) {
                            errorResponse = JSON.stringify({
                                error: 'Dashboard Error',
                                message: 'Dashboard route returned HTML instead of JSON. This may indicate a server error or authentication issue.',
                                status: xhr.status,
                                dashboard_id: dashboardId,
                                html_response: true
                            });
                        } else if (xhr.status >= 400) {
                            errorResponse = JSON.stringify({
                                error: 'Server Error',
                                message: `Request failed with status ${xhr.status}`,
                                status: xhr.status
                            });
                        } else {
                            errorResponse = JSON.stringify({}); // Empty object for successful but HTML responses
                        }
                        
                        // Override response properties
                        Object.defineProperty(xhr, 'responseText', {
                            value: errorResponse,
                            writable: false,
                            configurable: true
                        });
                        
                        Object.defineProperty(xhr, 'response', {
                            value: errorResponse,
                            writable: false,
                            configurable: true
                        });
                    } catch (e) {
                        console.error('Error converting HTML response to JSON:', e);
                    }
                } else {
                    // Try to parse as JSON to catch parse errors early
                    try {
                        JSON.parse(responseText);
                    } catch (parseError) {
                        // If it's a dashboard route and JSON parse fails, provide better error
                        if (isDashboardRoute) {
                            console.error(`Dashboard route ${xhr._url} returned invalid JSON. Status: ${xhr.status}`);
                            console.error(`Parse error: ${parseError.message}`);
                            console.error(`Response preview: ${trimmedResponse.substring(0, 200)}`);
                            
                            try {
                                const errorResponse = JSON.stringify({
                                    error: 'Dashboard Parse Error',
                                    message: `Failed to parse dashboard data: ${parseError.message}`,
                                    status: xhr.status,
                                    dashboard_id: dashboardId,
                                    parse_error: parseError.message
                                });
                                
                                Object.defineProperty(xhr, 'responseText', {
                                    value: errorResponse,
                                    writable: false,
                                    configurable: true
                                });
                                
                                Object.defineProperty(xhr, 'response', {
                                    value: errorResponse,
                                    writable: false,
                                    configurable: true
                                });
                            } catch (e) {
                                console.error('Error creating dashboard parse error response:', e);
                            }
                        }
                    }
                }
            }
        };
        
        xhr.onreadystatechange = function() {
            checkAndConvertResponse();
            
            // Call original handler
            if (originalOnReadyStateChange) {
                originalOnReadyStateChange.apply(this, arguments);
            }
        };
        
        // Also check on load
        if (originalOnLoad) {
            xhr.onload = function() {
                checkAndConvertResponse();
                originalOnLoad.apply(this, arguments);
            };
        } else {
            xhr.onload = function() {
                checkAndConvertResponse();
            };
        }
        
        // Keep error handler
        if (originalOnError) {
            xhr.onerror = originalOnError;
        }
        
        return originalXHRSend.apply(this, args);
    };
    
    
    
    console.log('RPC Error Handler initialized');
})();

