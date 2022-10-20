// ==UserScript==
// @name         Direct external engine analysis requests to localhost
// @author       Altimor
// @match        https://lichess.org/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=lichess.org
// @grant        GM_xmlhttpRequest
// @run-at       document-start
// ==/UserScript==

(function() {
    const LOCAL_ENDPOINT = "http://localhost:9666";
    const URL_REGEX = new RegExp("^https://engine.lichess.ovh(?<path>/api/external-engine/[^/]+/analyse)$");

    const originalFetch = unsafeWindow.fetch;

    unsafeWindow.fetch = async (url, request) => {
        const path = url.match(URL_REGEX)?.groups?.path;
        if (path == null)
            return originalFetch(url, request);

        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: request.method,
                url: LOCAL_ENDPOINT + path,
                headers: request.headers,
                data: request.body,
                responseType: "stream",
                onerror: r => reject(new TypeError()),
                onreadystatechange: r => {
                    if (r.readyState == GM_xmlhttpRequest.HEADERS_RECEIVED) {
                        resolve({
                            ok: r.status >= 200 && r.status < 300,
                            status: r.status,
                            body: r.response
                        });
                    }
                }
            });
        });
    };
})();