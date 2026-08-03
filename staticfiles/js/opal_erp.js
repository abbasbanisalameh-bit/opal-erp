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

/* ===== OPAL System Update File Actions V20260715 ===== */
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

    function findUpdatesTable() {
        return Array.from(document.querySelectorAll("table")).find(function (table) {
            const value = table.textContent || "";
            return value.includes("الاستعادة") && value.includes("Commit") && value.includes("الحجم");
        });
    }

    async function installBackupActions() {
        if (!window.location.pathname.startsWith("/settings/updates/")) {
            return;
        }
        const table = findUpdatesTable();
        if (!table) {
            return;
        }

        let response;
        try {
            response = await fetch("/settings/updates/files/api/", {
                credentials: "same-origin",
                cache: "no-store",
                headers: {"X-Requested-With": "XMLHttpRequest"}
            });
        } catch (error) {
            console.error("OPAL backup API failed", error);
            return;
        }
        if (!response.ok) {
            return;
        }

        const payload = await response.json();
        const files = Array.isArray(payload.files) ? payload.files : [];
        const headerRow = table.querySelector("thead tr");
        if (!headerRow) {
            return;
        }

        let actionHeader = headerRow.querySelector("[data-opal-file-actions-header]");
        if (!actionHeader) {
            const existingHeader = Array.from(headerRow.cells).find(function (cell) {
                return (cell.textContent || "").includes("التنزيل") || (cell.textContent || "").includes("الحذف");
            });
            actionHeader = existingHeader || document.createElement("th");
            actionHeader.textContent = "التنزيل والحذف";
            actionHeader.dataset.opalFileActionsHeader = "1";
            if (!existingHeader) {
                headerRow.appendChild(actionHeader);
            }
        }

        const rows = Array.from(table.querySelectorAll("tbody tr")).filter(function (row) {
            return row.cells.length > 0;
        });

        rows.forEach(function (row, index) {
            const rowText = row.textContent || "";
            const file = files.find(function (candidate) {
                return rowText.includes(candidate.filename || "");
            }) || files[index];

            let cell = row.querySelector("[data-opal-file-actions]");
            if (!cell) {
                const oldCell = Array.from(row.cells).find(function (item) {
                    const text = item.textContent || "";
                    return text.includes("الملف غير متاح") || text.includes("تنزيل") || text.includes("حذف");
                });
                cell = oldCell || document.createElement("td");
                cell.dataset.opalFileActions = "1";
                if (!oldCell) {
                    row.appendChild(cell);
                }
            }
            cell.innerHTML = "";

            if (!file) {
                cell.innerHTML = '<span class="text-secondary small">الملف غير موجود</span>';
                return;
            }

            const wrapper = document.createElement("div");
            wrapper.className = "opal-backup-file-actions";

            const download = document.createElement("a");
            download.className = "btn btn-sm btn-info";
            download.textContent = "تنزيل";
            download.href = "/settings/updates/files/download/?name=" + encodeURIComponent(file.name);
            download.setAttribute("download", file.filename || "opal-backup.zip");

            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "btn btn-sm btn-danger";
            remove.textContent = "حذف";
            remove.addEventListener("click", async function () {
                if (!window.confirm("حذف النسخة نهائيًا من ملفات الخادم؟\n\n" + (file.filename || file.name))) {
                    return;
                }
                remove.disabled = true;
                remove.textContent = "جاري الحذف...";
                const body = new URLSearchParams();
                body.set("name", file.name);
                try {
                    const deleteResponse = await fetch("/settings/updates/files/delete/", {
                        method: "POST",
                        credentials: "same-origin",
                        headers: {
                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                            "X-CSRFToken": getCookie("csrftoken"),
                            "X-Requested-With": "XMLHttpRequest"
                        },
                        body: body.toString()
                    });
                    const result = await deleteResponse.json();
                    if (!deleteResponse.ok || !result.ok) {
                        throw new Error(result.message || "تعذر حذف النسخة.");
                    }
                    row.remove();
                    window.alert("تم حذف النسخة وملف معلوماتها بنجاح.");
                } catch (error) {
                    remove.disabled = false;
                    remove.textContent = "حذف";
                    window.alert(error.message || "حدث خطأ أثناء الحذف.");
                }
            });

            wrapper.appendChild(download);
            wrapper.appendChild(remove);
            cell.appendChild(wrapper);
        });
    }

    function scheduleBackupActions() {
        [250, 900, 1800].forEach(function (delay) {
            window.setTimeout(installBackupActions, delay);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scheduleBackupActions);
    } else {
        scheduleBackupActions();
    }
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

    function updateClock() {
        const timeNode = document.getElementById("opal-clock-time");
        const dateNode = document.getElementById("opal-clock-date");
        if (!timeNode || !dateNode) return;
        const now = new Date();
        timeNode.textContent = new Intl.DateTimeFormat("ar-JO", {hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true}).format(now);
        dateNode.textContent = new Intl.DateTimeFormat("ar-JO", {weekday: "short", year: "numeric", month: "short", day: "numeric"}).format(now);
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
            if (bodyRows.length < 2) return;
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
        installBackButton();
        installInstantTableSearch();
        installLiveFilterForms();
        installTooltips();
        installExamScope();
    });
})();
