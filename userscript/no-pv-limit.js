// ==UserScript==
// @name         Show full PV lines
// @author       Altimor
// @match        https://lichess.org/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=lichess.org
// @run-at       document-start
// ==/UserScript==

(function() {
    function watchValue(obj, prop, onSet) {
        let real = prop in obj ? onSet(obj, obj[prop]) : undefined;

        Object.defineProperty(obj, prop, {
            configurable: true,
            enumerable: true,
            get: () => real,
            set: value => real = onSet(obj, value)
        });
    }

    function watchChain(obj, props, onSet) {
        if (typeof props == "string")
            props = props.split(".");

        if (props.length == 1) {
            watchValue(obj, props[0], onSet);
        } else if (props.length > 1) {
            watchValue(obj, props[0], (obj, value) => {
                watchChain(value, props.slice(1), onSet);
                return value;
            });
        }
    }

    watchChain(unsafeWindow, "lichess.analysis.ceval.opts.emit", (opts, emit) => {
        return function(ev, work) {
            for (const pvs of ev.pvs) {
                pvs.moves.slice = function(...args) {
                    if (args[0] === 0 && args[1] === 16)
                        return this;

                    return Array.prototype.slice.call(this, ...args);
                };
            }
            emit(ev, work);
        }
    });
}());