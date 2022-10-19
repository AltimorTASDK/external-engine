// ==UserScript==
// @name         Restore localhost external engine analysis
// @author       Altimor
// @match        https://lichess.org/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=lichess.org
// @grant        GM_xmlhttpRequest
// @run-at       document-start
// ==/UserScript==

(function() {
    var xhrWrapper = function() {
        var o = {headers: {}},
            t = this,
            sent = false,
            currentHeaders = "";

        t.channel = {
            name: ""
        };

        o.onprogress = function(r){
            if(r.lengthComputable) {
                t.channel.contentLength = r.total;
                currentHeaders = "Content-Length: " + r.total;
            }
            t.status = r.status;
            t.statusText = r.statusText;
            t.channel.name = r.finalUrl;
        };

        t.abort = function() {
            if(typeof o.abort == "function") o.abort();
            else t.onreadystatechange = null;
            sent = false;
        };
        t.getAllResponseHeaders = function() {
            return t.responseHeaders ? t.responseHeaders + (/(^|\n)Content-Length:\s?\d/i.test(t.responseHeaders)?"":"\n" + currentHeaders) : currentHeaders;
        };
        t.getResponseHeader = function(header) {
            console_log("Method not supported. getResponseHeader: " + header);
            return "";
        };
        t.open = function(method, url, async, user, password) {
            o.method = method;
            o.url = url;
            t.channel.name = url; //finalUrl?
            //o.synchronous = !async; //Not implemented for safety reasons
            if (typeof user != "undefined") o.user = user;
            if (typeof password != "undefined") o.password = password;
        };
        t.overrideMimeType = function(mimetype) {
            o.overrideMimeType = mimetype;
        };
        t.send = function(data){
            var readyState4reached = false;
            if (typeof t.onabort == "function") r.onabort = t.onabort;
            if (typeof t.onerror == "function") r.onerror = t.onerror;
            o.onload = function(r){
                o.onreadystatechange(r);
                if (typeof t.onload == "function") t.onload();
            };
            o.data = data;
            o.onreadystatechange = function(r) {
                t.channel.name = r.finalUrl;
                if (t.responseHeaders = r.responseHeaders) {
                    var tmp;
                    if(tmp = t.responseHeaders.match(/Content-Length:\s?(\d+)/i)) {
                        t.channel.contentLength = tmp[1];
                    }
                }
                t.readyState = r.readyState;
                t.responseText = r.responseText;
                t.status = r.status;
                t.statusText = r.statusText;
                if(readyState4reached) return;
                if(!readyState4reached && t.readyState == 4) readyState4reached = true;
                typeof t.onreadystatechange == "function" && t.onreadystatechange();
            }
            if(!sent) reqs.push(o);
            sent = true;
        };
        t.setRequestHeader = function(name, value) {
            o.headers[name] = value;
        };
    }

    xhrOriginal = unsafeWindow.XMLHttpRequest;
    unsafeWindow.XMLHttpRequest

    /*const REMOTE_ENDPOINT = "https://engine.lichess.ovh";
    const LOCAL_ENDPOINT  = "http://localhost:9666";
    const CSP_SELECTOR    = 'meta[http-equiv="Content-Security-Policy"]';

    function addLocalEndpointToCsp(node) {
        const content = node.attributes.content;
        content.value = content.value.replace("connect-src ", `connect-src ${LOCAL_ENDPOINT} `);
    }

    const scriptObserver = new MutationObserver(mutations => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.matches('script') && node.text.includes(REMOTE_ENDPOINT)) {
                    node.innerHTML = node.text.replace(REMOTE_ENDPOINT, LOCAL_ENDPOINT);
                    scriptObserver.disconnect();
                }
            }
        }
    });

    scriptObserver.observe(document.body, {childList: true});

    const cspNode = document.head.querySelector(CSP_SELECTOR);

    if (cspNode !== null) {
        addLocalEndpointToCsp(cspNode);
        return;
    }

    const metaObserver = new MutationObserver(mutations => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (document.head.querySelector(CSP_SELECTOR)) {
                    addLocalEndpointToCsp(node);
                    metaObserver.disconnect();
                }
            }
        }
    });

    metaObserver.observe(document.head, {childList: true});*/
})();