document.addEventListener("DOMContentLoaded", function () {

    console.log("OPAL School ERP Loaded");

    // تفعيل العنصر الحالي في القائمة
    document.querySelectorAll(".opal-menu a").forEach(link => {
        if (link.href === window.location.href) {
            link.classList.add("active");
        }
    });

    // إبقاء زر الوحدة الفعال في بؤرة شريط التمرير وإظهار الأزرار التالية له.
    document.querySelectorAll(".opal-module-subnav-scroll").forEach(function (bar) {
        const active = bar.querySelector(".opal-subnav-btn.active");
        if (!active) {
            return;
        }
        active.setAttribute("aria-current", "page");
        window.requestAnimationFrame(function () {
            active.scrollIntoView({behavior: "auto", block: "nearest", inline: "center"});
        });
        bar.querySelectorAll(".opal-subnav-btn").forEach(function (button) {
            button.addEventListener("click", function () {
                button.scrollIntoView({behavior: "smooth", block: "nearest", inline: "center"});
            });
        });
    });

});

/* Update 85: persistent dark/light preference.  No page reload is needed and
   the moon control remains in the same visual weight as the notification bell. */
(function () {
    "use strict";
    const storageKey = "opal-theme-mode";

    function applyTheme(mode) {
        const light = mode === "light";
        const resolved = light ? "light" : "dark";
        document.documentElement.setAttribute("data-opal-theme", resolved);
        document.documentElement.classList.toggle("opal-light-mode", light);
        document.documentElement.classList.toggle("opal-dark-mode", !light);
        document.body.classList.toggle("opal-light-mode", light);
        document.body.classList.toggle("opal-dark-mode", !light);
        const button = document.getElementById("opal-theme-toggle");
        if (!button) return;
        button.setAttribute("aria-pressed", String(light));
        button.setAttribute("aria-label", light ? "تفعيل الوضع الليلي" : "تفعيل الوضع النهاري");
        button.setAttribute("title", light ? "تفعيل الوضع الليلي" : "تفعيل الوضع النهاري");
        const icon = button.querySelector("i");
        if (icon) icon.className = light ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
    }

    document.addEventListener("DOMContentLoaded", function () {
        let saved = "";
        try { saved = window.localStorage.getItem(storageKey) || ""; } catch (_) {}
        applyTheme(saved === "light" ? "light" : "dark");
        const button = document.getElementById("opal-theme-toggle");
        if (!button) return;
        button.addEventListener("click", function () {
            const next = document.body.classList.contains("opal-light-mode") ? "dark" : "light";
            try { window.localStorage.setItem(storageKey, next); } catch (_) {}
            applyTheme(next);
        });
    });
})();

/* ===== OPAL PythonAnywhere Reload Center V1 ===== */
(function () {
    "use strict";

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (const item of cookies) {
            const cookie = item.trim();
            if (cookie.startsWith(name + "=")) {
                return decodeURIComponent(cookie.slice(name.length + 1));
            }
        }
        return "";
    }

    function replaceLegacyReloadInstructions() {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const replacements = [
            [
                "بعد أي استعادة ناجحة اضغط Reload من صفحة Web في PythonAnywhere.",
                "بعد أي استعادة ناجحة استخدم زر إعادة تحميل الموقع داخل هذا المركز."
            ],
            [
                "اضغط Reload من صفحة Web.",
                "استخدم زر إعادة تحميل الموقع داخل مركز التحديث."
            ]
        ];
        let node;
        while ((node = walker.nextNode())) {
            let value = node.nodeValue;
            replacements.forEach(function (item) {
                value = value.replace(item[0], item[1]);
            });
            node.nodeValue = value;
        }
    }

    function installReloadButton() {
        if (!window.location.pathname.startsWith("/settings/updates/") || document.getElementById("opalWebappReloadButton")) {
            return;
        }
        replaceLegacyReloadInstructions();
        const currentCard = document.querySelector(".opal-card");
        if (!currentCard) {
            return;
        }
        const host = currentCard.querySelector(".col-lg-4") || currentCard;
        const wrapper = document.createElement("div");
        wrapper.className = "mt-3 d-flex flex-column align-items-lg-end gap-2";

        const button = document.createElement("button");
        button.type = "button";
        button.id = "opalWebappReloadButton";
        button.className = "btn btn-success";
        button.innerHTML = '<i class="bi bi-arrow-repeat"></i> إعادة تحميل الموقع';

        const status = document.createElement("div");
        status.className = "small text-secondary";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        status.textContent = "يعيد تشغيل موقع PythonAnywhere دون فتح صفحة Web.";

        button.addEventListener("click", async function () {
            if (!window.confirm("إعادة تحميل موقع OPAL الآن؟ قد ينقطع الاتصال لعدة ثوانٍ.")) {
                return;
            }
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> جارٍ إرسال الطلب';
            status.className = "small text-info";
            status.textContent = "يتم إرسال أمر إعادة التحميل بأمان...";
            try {
                const response = await fetch("/settings/updates/reload/", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.message || "تعذر إعادة تحميل الموقع.");
                }
                status.className = "small text-success";
                status.textContent = payload.message + " سيتم تحديث الصفحة تلقائيًا خلال 10 ثوانٍ.";
                let seconds = 10;
                const countdown = window.setInterval(function () {
                    seconds -= 1;
                    button.innerHTML = '<i class="bi bi-arrow-clockwise"></i> تحديث تلقائي خلال ' + seconds;
                    if (seconds <= 0) {
                        window.clearInterval(countdown);
                        window.location.reload();
                    }
                }, 1000);
            } catch (error) {
                button.disabled = false;
                button.innerHTML = '<i class="bi bi-arrow-repeat"></i> إعادة تحميل الموقع';
                status.className = "small text-danger";
                status.textContent = error.message || "تعذر إعادة تحميل الموقع.";
            }
        });

        wrapper.append(button, status);
        host.appendChild(wrapper);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", installReloadButton, {once: true});
    } else {
        installReloadButton();
    }
})();

// OPAL_TABLE_SCROLL_INIT_V4 — compatibility marker
// OPAL_TABLE_SCROLL_LIGHT_V1
(function () {
    "use strict";

    function initializeScrollableTables() {
        document.querySelectorAll(".table-responsive, .table-wrap").forEach(function (container) {
            if (!container.querySelector("table")) {
                return;
            }
            container.classList.add("opal-table-scroll");
            if (!container.hasAttribute("tabindex")) {
                container.setAttribute("tabindex", "0");
            }
            container.setAttribute("role", "region");
            container.setAttribute("aria-label", "جدول قابل للتمرير");
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeScrollableTables, {once: true});
    } else {
        initializeScrollableTables();
    }
})();

/* ===== OPAL Audible Notifications V1 ===== */
(function () {
    "use strict";

    const bell = document.getElementById("opal-notification-bell");
    if (!bell) return;
    const statusUrl = bell.dataset.statusUrl;
    const badge = document.getElementById("opal-notification-badge");
    const storageKey = "opal:last-audible-notification";
    let audioUnlocked = false;
    let pendingId = bell.dataset.latestId || "";
    let pendingTitle = "";

    function lastPlayed() {
        try { return window.localStorage.getItem(storageKey) || ""; } catch (_) { return ""; }
    }
    function remember(id) {
        try { window.localStorage.setItem(storageKey, String(id || "")); } catch (_) {}
    }
    function beep() {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return false;
        try {
            const ctx = new AudioCtx();
            const gain = ctx.createGain();
            const oscillator = ctx.createOscillator();
            oscillator.type = "sine";
            oscillator.frequency.setValueAtTime(880, ctx.currentTime);
            oscillator.frequency.setValueAtTime(660, ctx.currentTime + 0.16);
            gain.gain.setValueAtTime(0.0001, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.38);
            oscillator.connect(gain);
            gain.connect(ctx.destination);
            oscillator.start();
            oscillator.stop(ctx.currentTime + 0.4);
            oscillator.addEventListener("ended", function () { ctx.close(); }, {once: true});
            return true;
        } catch (_) {
            return false;
        }
    }
    function playPending() {
        if (!audioUnlocked || !pendingId || String(pendingId) === lastPlayed()) return;
        if (beep()) {
            remember(pendingId);
            bell.setAttribute("title", pendingTitle ? "إشعار جديد: " + pendingTitle : "يوجد إشعار جديد");
        }
    }
    function unlockAudio() {
        audioUnlocked = true;
        playPending();
    }
    ["click", "touchstart", "keydown"].forEach(function (eventName) {
        document.addEventListener(eventName, unlockAudio, {once: true, passive: true});
    });
    function updateBadge(count) {
        if (!badge) return;
        badge.textContent = String(count || 0);
        badge.classList.toggle("d-none", !count);
    }
    async function poll() {
        if (!statusUrl || document.hidden) return;
        try {
            const response = await fetch(statusUrl, {
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
                cache: "no-store"
            });
            if (!response.ok) return;
            const payload = await response.json();
            updateBadge(payload.unread_count);
            if (payload.latest_id) {
                pendingId = String(payload.latest_id);
                pendingTitle = payload.latest_title || "";
                playPending();
            }
        } catch (_) {}
    }
    window.setInterval(poll, 30000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });
    poll();
})();

/* ===== OPAL Professional Action Icons V1 ===== */
(function () {
    "use strict";

    const iconRules = [
        {pattern: /حذف|إزالة|إلغاء نهائي|مسح/, icon: "bi-trash3-fill"},
        {pattern: /حفظ|تأكيد|اعتماد|تحديث/, icon: "bi-check2-circle"},
        {pattern: /إضافة|إنشاء|جديد|تسجيل طالب/, icon: "bi-plus-circle-fill"},
        {pattern: /تعديل|تحرير/, icon: "bi-pencil-square"},
        {pattern: /بحث|ابحث/, icon: "bi-search"},
        {pattern: /تصفية|فلتر/, icon: "bi-funnel-fill"},
        {pattern: /تصدير|Excel|CSV/, icon: "bi-file-earmark-spreadsheet-fill"},
        {pattern: /تنزيل|تحميل/, icon: "bi-download"},
        {pattern: /طباعة/, icon: "bi-printer-fill"},
        {pattern: /رجوع|عودة/, icon: "bi-arrow-return-right"},
        {pattern: /إرسال|تعميم|تنبيه/, icon: "bi-send-fill"},
        {pattern: /تشغيل|تفعيل/, icon: "bi-play-circle-fill"},
        {pattern: /إيقاف|تعطيل/, icon: "bi-pause-circle-fill"},
        {pattern: /عرض|فتح|تفاصيل/, icon: "bi-eye-fill"},
        {pattern: /دخول/, icon: "bi-box-arrow-in-left"},
        {pattern: /دفع|دفعة|تحصيل/, icon: "bi-cash-coin"},
        {pattern: /إيصال/, icon: "bi-receipt-cutoff"},
        {pattern: /رفع/, icon: "bi-cloud-arrow-up-fill"},
        {pattern: /استعادة/, icon: "bi-arrow-counterclockwise"}
    ];

    function decorateButton(button) {
        if (!(button instanceof Element) || button.dataset.opalNoAutoIcon === "1") return;
        if (button.querySelector(":scope > .bi, :scope > .spinner-border, :scope > svg")) return;
        const label = (button.textContent || button.value || "").replace(/\s+/g, " ").trim();
        if (!label) return;
        const rule = iconRules.find(function (item) { return item.pattern.test(label); });
        if (!rule) return;
        const icon = document.createElement("i");
        icon.className = "bi " + rule.icon + " opal-auto-action-icon";
        icon.setAttribute("aria-hidden", "true");
        button.prepend(icon);
        button.classList.add("opal-action-button");
    }

    function decorateWithin(root) {
        if (!root || !(root instanceof Element || root instanceof Document)) return;
        if (root instanceof Element && root.matches(".btn, .primary-btn")) decorateButton(root);
        root.querySelectorAll(".btn, .primary-btn").forEach(decorateButton);
    }

    function initialize() {
        decorateWithin(document);
        const observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                mutation.addedNodes.forEach(function (node) {
                    if (node.nodeType === Node.ELEMENT_NODE) decorateWithin(node);
                });
            });
        });
        observer.observe(document.body, {childList: true, subtree: true});
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize, {once: true});
    } else {
        initialize();
    }
})();

/* ===== OPAL Canonical Operation Search V1 ===== */
(function () {
    "use strict";

    function normalize(value) {
        return String(value || "")
            .toLocaleLowerCase("ar")
            .replace(/[أإآ]/g, "ا")
            .replace(/ة/g, "ه")
            .replace(/ى/g, "ي")
            .replace(/\s+/g, " ")
            .trim();
    }

    function initializeOperationSearch() {
        const input = document.getElementById("opal-global-operation-search");
        const results = document.getElementById("opal-global-operation-results");
        const dataNode = document.getElementById("opal-operation-catalog");
        if (!input || !results || !dataNode) return;

        let operations = [];
        try {
            operations = JSON.parse(dataNode.textContent || "[]");
        } catch (_) {
            operations = [];
        }
        if (!Array.isArray(operations)) operations = [];

        let activeIndex = -1;
        let rendered = [];

        function closeResults() {
            results.classList.add("d-none");
            results.innerHTML = "";
            rendered = [];
            activeIndex = -1;
            input.setAttribute("aria-expanded", "false");
        }

        function activate(index) {
            const items = Array.from(results.querySelectorAll("a"));
            if (!items.length) return;
            activeIndex = Math.max(0, Math.min(index, items.length - 1));
            items.forEach(function (item, itemIndex) {
                item.classList.toggle("active", itemIndex === activeIndex);
            });
            items[activeIndex].scrollIntoView({block: "nearest"});
        }

        function draw() {
            const query = normalize(input.value);
            if (!query) {
                closeResults();
                return;
            }
            rendered = operations.filter(function (operation) {
                return normalize(operation.search_text || operation.label || "").includes(query);
            }).slice(0, 9);

            results.innerHTML = "";
            if (!rendered.length) {
                const empty = document.createElement("div");
                empty.className = "opal-global-operation-empty";
                empty.textContent = "لم يتم العثور على عملية مطابقة.";
                results.appendChild(empty);
            } else {
                rendered.forEach(function (operation) {
                    const link = document.createElement("a");
                    link.href = operation.url;
                    link.setAttribute("role", "option");

                    const icon = document.createElement("i");
                    icon.className = "bi bi-" + (operation.icon || "arrow-left-circle");
                    const copy = document.createElement("span");
                    const title = document.createElement("strong");
                    title.textContent = operation.label;
                    const meta = document.createElement("small");
                    meta.textContent = operation.module_label + " — " + operation.description;
                    copy.append(title, meta);
                    const arrow = document.createElement("i");
                    arrow.className = "bi bi-arrow-left-short opal-search-arrow";
                    link.append(icon, copy, arrow);
                    results.appendChild(link);
                });
            }
            results.classList.remove("d-none");
            input.setAttribute("aria-expanded", "true");
            activeIndex = -1;
        }

        input.addEventListener("input", draw);
        input.addEventListener("keydown", function (event) {
            if (event.key === "ArrowDown") {
                event.preventDefault();
                activate(activeIndex + 1);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                activate(activeIndex <= 0 ? rendered.length - 1 : activeIndex - 1);
            } else if (event.key === "Enter" && rendered.length) {
                event.preventDefault();
                const target = rendered[activeIndex >= 0 ? activeIndex : 0];
                window.location.assign(target.url);
            } else if (event.key === "Escape") {
                closeResults();
                input.blur();
            }
        });

        document.addEventListener("keydown", function (event) {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                input.focus();
                input.select();
            }
        });
        document.addEventListener("click", function (event) {
            if (!event.target.closest(".opal-global-search-wrap")) closeResults();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeOperationSearch, {once: true});
    } else {
        initializeOperationSearch();
    }
})();

/* ===== OPAL Unified UX 2026-07 ===== */
(function () {
    "use strict";

    function ready(callback) {
        if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", callback, {once: true});
        else callback();
    }

    const opalClockZone = document.documentElement.dataset.opalTimeZone || "Asia/Amman";
    const opalServerStart = Date.parse(document.documentElement.dataset.opalServerNow || "");
    const opalClientStart = Date.now();

    function officialNow() {
        if (Number.isFinite(opalServerStart)) {
            return new Date(opalServerStart + (Date.now() - opalClientStart));
        }
        return new Date();
    }

    function formatOfficialDate(value, options) {
        try {
            return new Intl.DateTimeFormat("ar-JO", Object.assign({timeZone: opalClockZone}, options)).format(value);
        } catch (error) {
            return new Intl.DateTimeFormat("ar-JO", Object.assign({timeZone: "Asia/Amman"}, options)).format(value);
        }
    }

    function updateClock() {
        const timeNode = document.getElementById("opal-clock-time");
        const dateNode = document.getElementById("opal-clock-date");
        const now = officialNow();
        const officialTime = formatOfficialDate(now, {hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true});
        const officialDate = formatOfficialDate(now, {weekday: "short", year: "numeric", month: "short", day: "numeric"});
        if (timeNode) timeNode.textContent = officialTime;
        if (dateNode) dateNode.textContent = officialDate;
        document.querySelectorAll('[data-opal-official-clock="time"]').forEach(function (node) {
            node.textContent = officialTime;
        });
        document.querySelectorAll('[data-opal-official-clock="date"]').forEach(function (node) {
            node.textContent = officialDate;
        });
    }

    function installLiveBoundaryRefresh() {
        const seconds = Array.from(document.querySelectorAll("[data-live-seconds]"))
            .map(function (node) { return Number.parseInt(node.dataset.liveSeconds || "", 10); })
            .filter(function (value) { return Number.isFinite(value) && value >= 0; });
        if (!seconds.length) return;
        const nearestBoundary = Math.min.apply(null, seconds);
        window.setTimeout(function () { window.location.reload(); }, (nearestBoundary + 1) * 1000);
    }

    function installBackButton() {
        const button = document.querySelector(".opal-dynamic-back");
        if (!button) return;
        button.addEventListener("click", function () {
            const sameOriginReferrer = document.referrer && new URL(document.referrer).origin === window.location.origin;
            if (sameOriginReferrer && window.history.length > 1) window.history.back();
            else window.location.href = button.dataset.fallbackUrl || "/";
        });
    }

    function installInstantTableSearch() {
        document.querySelectorAll("table[data-opal-instant-table], table.opal-table, table.table").forEach(function (table, index) {
            if (table.dataset.opalSearchReady === "1" || table.dataset.opalInstantTable === "off") return;
            const bodyRows = table.querySelectorAll("tbody tr");
            if (bodyRows.length < 30 || table.querySelector("tbody [colspan]")) return;
            table.dataset.opalSearchReady = "1";
            const wrapper = table.closest(".table-responsive, .table-wrap") || table.parentElement;
            if (!wrapper) return;
            const bar = document.createElement("div");
            bar.className = "opal-instant-table-search";
            bar.innerHTML = '<i class="bi bi-search"></i><input type="search" class="form-control" placeholder="بحث فوري داخل الجدول..." aria-label="بحث فوري داخل الجدول"><span class="opal-table-result-count"></span>';
            wrapper.parentNode.insertBefore(bar, wrapper);
            const input = bar.querySelector("input");
            const count = bar.querySelector(".opal-table-result-count");
            const rows = Array.from(table.querySelectorAll("tbody tr"));
            function filter() {
                const query = (input.value || "").trim().toLocaleLowerCase("ar");
                let visible = 0;
                rows.forEach(function (row) {
                    const show = !query || (row.textContent || "").toLocaleLowerCase("ar").includes(query);
                    row.classList.toggle("d-none", !show);
                    if (show) visible += 1;
                });
                count.textContent = visible + " نتيجة";
            }
            input.addEventListener("input", filter);
            filter();
        });
    }

    function installLiveFilterForms() {
        document.querySelectorAll("form[data-live-filter], form[method=\"get\"]:not([data-live-filter=\"off\"])").forEach(function (form) {
            if (form.dataset.liveReady === "1") return;
            form.dataset.liveReady = "1";
            let timer = null;
            function submitSoon(delay) {
                window.clearTimeout(timer);
                timer = window.setTimeout(function () {
                    if (typeof form.requestSubmit === "function") form.requestSubmit();
                    else form.submit();
                }, delay);
            }
            form.querySelectorAll("select").forEach(function (field) {
                field.addEventListener("change", function () { submitSoon(80); });
            });
            form.querySelectorAll('input[type="search"], input[name="q"]').forEach(function (field) {
                field.addEventListener("input", function () { submitSoon(450); });
            });
        });
    }

    function installTooltips() {
        document.querySelectorAll(".btn, .opal-card, .opal-module-card, .icon-btn").forEach(function (element) {
            if (!element.getAttribute("title")) {
                const text = (element.getAttribute("aria-label") || element.querySelector("h3,h4,h5,strong")?.textContent || element.textContent || "").replace(/\s+/g, " ").trim();
                if (text && text.length <= 100) element.setAttribute("title", text);
            }
        });
        if (window.bootstrap && window.bootstrap.Tooltip) {
            document.querySelectorAll('[title]:not([data-opal-tooltip-ready="1"])').forEach(function (element) {
                element.dataset.opalTooltipReady = "1";
                new window.bootstrap.Tooltip(element, {container: "body", trigger: "hover focus", delay: {show: 350, hide: 80}});
            });
        }
    }

    function installExamScope() {
        const summary = document.getElementById("opal-exam-teacher-summary");
        const teacherName = document.getElementById("opal-exam-teacher-name");
        if (!summary || !teacherName || !summary.dataset.scopeUrl) return;
        const form = summary.closest("form") || document;
        const fields = {};
        form.querySelectorAll("[data-exam-scope-field]").forEach(function (field) { fields[field.dataset.examScopeField] = field; });
        function replaceOptions(select, items, placeholder, selectedValue) {
            if (!select) return;
            const previous = selectedValue || select.value;
            select.innerHTML = "";
            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = placeholder;
            select.appendChild(empty);
            (items || []).forEach(function (item) {
                const option = document.createElement("option");
                option.value = String(item.id);
                option.textContent = item.label + (item.current ? " — الحالي" : "");
                option.selected = String(item.id) === String(previous);
                select.appendChild(option);
            });
        }
        async function refresh(changed) {
            const params = new URLSearchParams();
            ["academic_year", "grade", "section", "subject"].forEach(function (name) {
                if (fields[name]?.value) params.set(name, fields[name].value);
            });
            try {
                const response = await fetch(summary.dataset.scopeUrl + "?" + params.toString(), {headers: {"X-Requested-With": "XMLHttpRequest"}});
                if (!response.ok) return;
                const payload = await response.json();
                if (changed === "academic_year") replaceOptions(fields.semester, payload.semesters, "اختر الفصل", "");
                if (changed === "academic_year" || changed === "grade") {
                    replaceOptions(fields.section, payload.sections, "اختر الشعبة", changed === "grade" ? "" : fields.section?.value);
                    replaceOptions(fields.subject, payload.subjects, "اختر المادة", changed === "grade" ? "" : fields.subject?.value);
                }
                teacherName.textContent = payload.teacher ? payload.teacher.name : "لا يوجد تكليف فعال مطابق";
                summary.classList.toggle("is-missing", !payload.teacher);
            } catch (_) {
                teacherName.textContent = "تعذر قراءة التكليف حاليًا";
            }
        }
        Object.keys(fields).forEach(function (name) {
            fields[name].addEventListener("change", function () { refresh(name); });
        });
        refresh("");
    }

    ready(function () {
        updateClock();
        window.setInterval(updateClock, 1000);
        installLiveBoundaryRefresh();
        installBackButton();
        installInstantTableSearch();
        installLiveFilterForms();
        installTooltips();
        installExamScope();
    });
})();

/* ===== OPAL Update 95: accessible mobile sidebar ===== */
(function () {
    "use strict";

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback, {once: true});
        } else {
            callback();
        }
    }

    ready(function () {
        const body = document.body;
        const sidebar = document.getElementById("opal-sidebar");
        const toggle = document.getElementById("opal-sidebar-toggle");
        const closeButton = document.getElementById("opal-sidebar-close");
        const overlay = document.getElementById("opal-sidebar-overlay");
        const mobileQuery = window.matchMedia("(max-width: 900px)");

        if (!sidebar || !toggle || !overlay) return;

        function setOpen(open, restoreFocus) {
            if (!mobileQuery.matches) open = false;
            body.classList.toggle("opal-sidebar-open", open);
            toggle.setAttribute("aria-expanded", String(open));
            sidebar.setAttribute("aria-hidden", String(!open && mobileQuery.matches));
            if (open) {
                const first = sidebar.querySelector("a, button");
                window.setTimeout(function () { if (first) first.focus({preventScroll: true}); }, 50);
            } else if (restoreFocus) {
                toggle.focus({preventScroll: true});
            }
        }

        toggle.addEventListener("click", function () {
            setOpen(!body.classList.contains("opal-sidebar-open"), false);
        });
        overlay.addEventListener("click", function () { setOpen(false, true); });
        if (closeButton) closeButton.addEventListener("click", function () { setOpen(false, true); });

        sidebar.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                if (mobileQuery.matches) setOpen(false, false);
            });
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && body.classList.contains("opal-sidebar-open")) {
                setOpen(false, true);
            }
        });

        function syncViewport() {
            setOpen(false, false);
            sidebar.setAttribute("aria-hidden", String(mobileQuery.matches));
        }
        if (mobileQuery.addEventListener) mobileQuery.addEventListener("change", syncViewport);
        else mobileQuery.addListener(syncViewport);
        syncViewport();
    });
})();

/* ===== OPAL Update 120: Unified interaction feedback and state continuity ===== */
(function () {
    "use strict";

    const submittingClass = "opal-form-submitting";
    const navigationClass = "opal-navigation-pending";
    const scrollPrefix = "opal:scroll:";
    const tableSearchPrefix = "opal:table-search:";

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback, {once: true});
        } else {
            callback();
        }
    }

    function safeSessionGet(key) {
        try { return window.sessionStorage.getItem(key) || ""; } catch (_) { return ""; }
    }

    function safeSessionSet(key, value) {
        try { window.sessionStorage.setItem(key, String(value)); } catch (_) {}
    }

    function statusNode() {
        return document.getElementById("opal-ux-status");
    }

    function announce(message, tone) {
        const node = statusNode();
        if (!node || !message) return;
        node.textContent = message;
        node.dataset.tone = tone || "info";
        node.classList.add("is-visible");
        window.clearTimeout(node._opalHideTimer);
        node._opalHideTimer = window.setTimeout(function () {
            node.classList.remove("is-visible");
        }, 5000);
    }

    function resetNavigationFeedback() {
        document.documentElement.classList.remove(navigationClass);
        const main = document.querySelector(".opal-main");
        if (main) main.removeAttribute("aria-busy");
    }

    function beginNavigation(label) {
        if (document.documentElement.classList.contains(navigationClass)) return;
        document.documentElement.classList.add(navigationClass);
        const main = document.querySelector(".opal-main");
        if (main) main.setAttribute("aria-busy", "true");
        announce(label ? "جارٍ فتح " + label + "…" : "جارٍ فتح الصفحة…", "info");
    }

    function samePageHashOnly(url) {
        return url.pathname === window.location.pathname &&
            url.search === window.location.search &&
            Boolean(url.hash);
    }

    function eligibleNavigationLink(link, event) {
        if (!link || event.defaultPrevented || event.button !== 0) return false;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
        if (link.target && link.target !== "_self") return false;
        if (link.hasAttribute("download") || link.dataset.opalNavigationFeedback === "off") return false;
        const raw = link.getAttribute("href") || "";
        if (!raw || raw.startsWith("#") || raw.startsWith("javascript:") || raw.startsWith("mailto:") || raw.startsWith("tel:")) return false;
        let url;
        try { url = new URL(link.href, window.location.href); } catch (_) { return false; }
        if (url.origin !== window.location.origin || samePageHashOnly(url)) return false;
        return true;
    }

    function installNavigationFeedback() {
        document.addEventListener("click", function (event) {
            const link = event.target.closest("a[href]");
            if (!eligibleNavigationLink(link, event)) return;
            const label = (link.dataset.busyLabel || link.getAttribute("aria-label") || link.getAttribute("title") || link.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80);
            beginNavigation(label);
        });
        window.addEventListener("pageshow", resetNavigationFeedback);
        window.addEventListener("beforeunload", function () {
            if (!document.documentElement.classList.contains(navigationClass)) beginNavigation("");
        });
    }

    function snapshotSubmitButtons() {
        document.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (button) {
            if (button.dataset.opalOriginalDisabled !== undefined) return;
            button.dataset.opalOriginalDisabled = button.disabled ? "1" : "0";
            if (button.tagName === "INPUT") {
                button.dataset.opalOriginalValue = button.value || "";
            } else {
                button.dataset.opalOriginalHtml = button.innerHTML;
            }
        });
    }

    function resetForm(form) {
        if (!form) return;
        delete form.dataset.opalSubmitting;
        form.classList.remove(submittingClass);
        form.removeAttribute("aria-busy");
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (button) {
            button.removeAttribute("aria-disabled");
            if (button.dataset.opalOriginalValue !== undefined && button.tagName === "INPUT") {
                button.value = button.dataset.opalOriginalValue;
            } else if (button.dataset.opalOriginalHtml !== undefined) {
                button.innerHTML = button.dataset.opalOriginalHtml;
            }
            button.disabled = button.dataset.opalOriginalDisabled === "1";
        });
    }

    function markFormSubmitting(form, submitter) {
        form.dataset.opalSubmitting = "1";
        form.classList.add(submittingClass);
        form.setAttribute("aria-busy", "true");
        const button = submitter || form.querySelector('button[type="submit"], input[type="submit"]');
        if (button) {
            button.setAttribute("aria-disabled", "true");
            const busyLabel = button.dataset.busyLabel || "جارٍ التنفيذ…";
            if (button.tagName === "INPUT") {
                button.value = busyLabel;
            } else {
                button.textContent = "";
                const spinner = document.createElement("span");
                spinner.className = "spinner-border spinner-border-sm opal-submit-spinner";
                spinner.setAttribute("aria-hidden", "true");
                const label = document.createElement("span");
                label.textContent = busyLabel;
                button.append(spinner, label);
            }
            announce(busyLabel, "info");
        } else {
            announce("جارٍ تنفيذ العملية…", "info");
        }
    }

    function installSubmitGuard() {
        snapshotSubmitButtons();
        document.addEventListener("submit", function (event) {
            const form = event.target;
            if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
            const method = (form.getAttribute("method") || "get").toLowerCase();
            if (method === "get" || form.dataset.opalSubmitGuard === "off") return;
            if (form.dataset.opalSubmitting === "1") {
                event.preventDefault();
                announce("العملية قيد التنفيذ بالفعل؛ يرجى الانتظار.", "warning");
                return;
            }
            markFormSubmitting(form, event.submitter || null);
        });
        document.addEventListener("invalid", function (event) {
            const field = event.target;
            if (!(field instanceof HTMLElement)) return;
            announce("يرجى استكمال الحقول المطلوبة أو تصحيح القيم المحددة.", "warning");
            window.setTimeout(function () {
                field.scrollIntoView({behavior: "smooth", block: "center"});
            }, 30);
        }, true);
        window.addEventListener("pageshow", function () {
            document.querySelectorAll("form." + submittingClass + ', form[data-opal-submitting="1"]').forEach(resetForm);
        });
    }

    function installClickableCards() {
        document.querySelectorAll("[data-opal-card-link]").forEach(function (card) {
            if (card.dataset.opalCardReady === "1") return;
            const href = card.dataset.opalCardLink;
            if (!href) return;
            card.dataset.opalCardReady = "1";
            card.classList.add("opal-clickable-card");
            if (!card.hasAttribute("tabindex")) card.tabIndex = 0;
            if (!card.hasAttribute("role")) card.setAttribute("role", "link");
            function openCard(event) {
                if (event.target.closest("a, button, input, select, textarea, summary, form")) return;
                beginNavigation(card.getAttribute("aria-label") || card.textContent.replace(/\s+/g, " ").trim().slice(0, 60));
                window.location.assign(href);
            }
            card.addEventListener("click", openCard);
            card.addEventListener("keydown", function (event) {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                openCard(event);
            });
        });
    }

    function installPersistentInstantSearch() {
        document.querySelectorAll(".opal-instant-table-search").forEach(function (bar, index) {
            if (bar.dataset.opalPersistenceReady === "1") return;
            const input = bar.querySelector('input[type="search"]');
            if (!input) return;
            bar.dataset.opalPersistenceReady = "1";
            const key = tableSearchPrefix + window.location.pathname + window.location.search + ":" + index;
            const saved = safeSessionGet(key);
            if (saved) {
                input.value = saved;
                input.dispatchEvent(new Event("input", {bubbles: true}));
            }
            input.addEventListener("input", function () { safeSessionSet(key, input.value || ""); });
            const clear = document.createElement("button");
            clear.type = "button";
            clear.className = "opal-table-search-clear";
            clear.setAttribute("aria-label", "مسح البحث داخل الجدول");
            clear.setAttribute("title", "مسح البحث");
            clear.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';
            clear.addEventListener("click", function () {
                input.value = "";
                safeSessionSet(key, "");
                input.dispatchEvent(new Event("input", {bubbles: true}));
                input.focus();
            });
            bar.appendChild(clear);
        });
    }

    function installEmptyStates() {
        document.querySelectorAll("table tbody").forEach(function (body) {
            const rows = Array.from(body.rows || []);
            if (rows.length !== 1) return;
            const row = rows[0];
            const cells = Array.from(row.cells || []);
            if (cells.length !== 1 || row.querySelector("a, button, form, input, select")) return;
            const cell = cells[0];
            const message = (cell.textContent || "").replace(/\s+/g, " ").trim();
            if (!/^(لا توجد|لا يوجد|لم يتم العثور|لا تتوفر)/.test(message)) return;
            row.classList.add("opal-empty-row");
            cell.textContent = "";
            const state = document.createElement("div");
            state.className = "opal-empty-state";
            const icon = document.createElement("i");
            icon.className = "bi bi-inbox";
            icon.setAttribute("aria-hidden", "true");
            const title = document.createElement("strong");
            title.textContent = message;
            const hint = document.createElement("small");
            hint.textContent = "ستظهر البيانات هنا تلقائيًا عند توفرها.";
            state.append(icon, title, hint);
            cell.appendChild(state);
        });
    }

    function installBackScrollContinuity() {
        const key = scrollPrefix + window.location.href;
        window.addEventListener("pagehide", function () {
            safeSessionSet(key, Math.max(0, Math.round(window.scrollY || 0)));
        });
        window.addEventListener("pageshow", function (event) {
            const nav = window.performance && performance.getEntriesByType ? performance.getEntriesByType("navigation")[0] : null;
            const returning = Boolean(event.persisted || (nav && nav.type === "back_forward"));
            if (!returning) return;
            const saved = Number(safeSessionGet(key));
            if (!Number.isFinite(saved) || saved <= 0) return;
            window.requestAnimationFrame(function () { window.scrollTo({top: saved, behavior: "auto"}); });
        });
    }

    ready(function () {
        installNavigationFeedback();
        installSubmitGuard();
        installClickableCards();
        installPersistentInstantSearch();
        installEmptyStates();
        installBackScrollContinuity();
    });
})();

/* ===== OPAL Update 121: Mobile-first operational experience ===== */
(function () {
    "use strict";

    const phoneQuery = window.matchMedia("(max-width: 575px)");
    const complexTablePattern = /(calendar|matrix|gradebook|marks|schedule-grid|timetable-grid|print-table|opal-keep-grid)/i;
    const actionHeaderPattern = /(إجراء|الإجراء|الإجراءات|تحكم|خيارات|عملية)/;

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback, {once: true});
        } else {
            callback();
        }
    }

    function normalizedText(node) {
        return (node && node.textContent ? node.textContent : "").replace(/\s+/g, " ").trim();
    }

    function setVisualViewportMetrics() {
        const viewport = window.visualViewport;
        const height = Math.max(320, Math.round(viewport ? viewport.height : window.innerHeight));
        document.documentElement.style.setProperty("--opal-visual-viewport-height", height + "px");
        if (!document.body) return;
        const keyboardOpen = Boolean(viewport && phoneQuery.matches && (window.innerHeight - viewport.height) > 150);
        document.body.classList.toggle("opal-keyboard-open", keyboardOpen);
    }

    function isComplexTable(table, headers) {
        const mode = table.dataset.opalMobileTable || "";
        if (mode === "scroll" || table.classList.contains("opal-no-mobile-cards")) return true;
        if (mode === "cards") return false;
        const identity = [table.id, table.className, table.getAttribute("aria-label") || ""].join(" ");
        if (complexTablePattern.test(identity)) return true;
        if (table.querySelector("table")) return true;
        if (table.querySelector("thead [rowspan]:not([rowspan='1']), thead [colspan]:not([colspan='1'])")) return true;
        if (headers.length < 2 || headers.length > 9) return true;
        return false;
    }

    function markScrollableTable(table) {
        const wrapper = table.closest(".table-responsive, .opal-table-wrap, .table-wrap");
        if (!wrapper) return;
        wrapper.classList.add("opal-mobile-scroll-table");
        if (wrapper.querySelector(":scope > .opal-mobile-scroll-hint")) return;
        const hint = document.createElement("div");
        hint.className = "opal-mobile-scroll-hint";
        hint.setAttribute("aria-hidden", "true");
        hint.innerHTML = '<i class="bi bi-arrows-expand" aria-hidden="true"></i><span>اسحب أفقيًا لعرض بقية الجدول</span>';
        wrapper.insertBefore(hint, wrapper.firstChild);
    }

    function decorateTable(table) {
        if (!(table instanceof HTMLTableElement) || table.dataset.opalMobileReady === "1") return;
        table.dataset.opalMobileReady = "1";
        const headerRow = table.tHead && table.tHead.rows ? table.tHead.rows[0] : null;
        const headers = headerRow ? Array.from(headerRow.cells).map(normalizedText) : [];
        if (isComplexTable(table, headers)) {
            markScrollableTable(table);
            return;
        }

        const body = table.tBodies && table.tBodies[0];
        if (!body) return;
        table.classList.add("opal-mobile-card-table");
        const wrapper = table.closest(".table-responsive, .opal-table-wrap, .table-wrap");
        if (wrapper) wrapper.classList.add("opal-mobile-card-table-wrap");

        Array.from(body.rows).forEach(function (row) {
            const cells = Array.from(row.cells || []);
            const emptyState = cells.length === 1 && Number(cells[0].colSpan || 1) > 1;
            row.classList.toggle("opal-mobile-empty-table-row", emptyState);
            if (emptyState) return;
            cells.forEach(function (cell, index) {
                const label = headers[index] || "بيان";
                cell.dataset.opalLabel = label;
                if (actionHeaderPattern.test(label)) cell.classList.add("opal-mobile-actions-cell");
            });
        });
    }

    function enhanceTables(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll("table.opal-table, .table-responsive > table, .opal-table-wrap > table, .table-wrap > table, table[data-opal-mobile-table]").forEach(decorateTable);
    }

    function enhanceMobileActionAreas(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll(".opal-form-footer").forEach(function (footer) {
            footer.classList.add("opal-mobile-action-dock");
        });
        scope.querySelectorAll(".opal-section-actions").forEach(function (actions) {
            actions.classList.add("opal-mobile-section-actions");
        });
    }

    function installMobileFocusContinuity() {
        document.addEventListener("focusin", function (event) {
            const field = event.target;
            if (!phoneQuery.matches || !(field instanceof HTMLElement) || !field.matches("input, select, textarea")) return;
            window.setTimeout(function () {
                const rect = field.getBoundingClientRect();
                const visibleHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
                if (rect.bottom > visibleHeight - 24 || rect.top < 10) {
                    field.scrollIntoView({behavior: "smooth", block: "center"});
                }
            }, 180);
        });
    }

    function installMutationEnhancer() {
        if (!("MutationObserver" in window)) return;
        let scheduled = false;
        const observer = new MutationObserver(function (mutations) {
            if (scheduled || !mutations.some(function (item) { return item.addedNodes && item.addedNodes.length; })) return;
            scheduled = true;
            window.requestAnimationFrame(function () {
                scheduled = false;
                enhanceTables(document);
                enhanceMobileActionAreas(document);
            });
        });
        observer.observe(document.body, {childList: true, subtree: true});
    }

    ready(function () {
        setVisualViewportMetrics();
        enhanceTables(document);
        enhanceMobileActionAreas(document);
        installMobileFocusContinuity();
        installMutationEnhancer();

        window.addEventListener("resize", setVisualViewportMetrics, {passive: true});
        window.addEventListener("orientationchange", setVisualViewportMetrics, {passive: true});
        window.addEventListener("pageshow", setVisualViewportMetrics);
        if (window.visualViewport) {
            window.visualViewport.addEventListener("resize", setVisualViewportMetrics, {passive: true});
            window.visualViewport.addEventListener("scroll", setVisualViewportMetrics, {passive: true});
        }
    });
})();

/* ===== OPAL Update 131.7 R10: aesthetic finishing touches ===== */
(function () {
    "use strict";

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback, {once: true});
        } else {
            callback();
        }
    }

    ready(function () {
        const button = document.getElementById("opal-scroll-top");
        if (!button) return;

        const main = document.getElementById("opal-main-content");
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
        let updateScheduled = false;

        function syncVisibility() {
            updateScheduled = false;
            const visible = Math.max(window.scrollY || 0, document.documentElement.scrollTop || 0) > 420;
            button.classList.toggle("is-visible", visible);
            button.setAttribute("aria-hidden", visible ? "false" : "true");
            button.tabIndex = visible ? 0 : -1;
        }

        function scheduleVisibilitySync() {
            if (updateScheduled) return;
            updateScheduled = true;
            window.requestAnimationFrame(syncVisibility);
        }

        button.addEventListener("click", function () {
            window.scrollTo({top: 0, behavior: reducedMotion.matches ? "auto" : "smooth"});
            if (main) main.focus({preventScroll: true});
        });

        window.addEventListener("scroll", scheduleVisibilitySync, {passive: true});
        window.addEventListener("pageshow", syncVisibility);
        syncVisibility();
    });
})();
