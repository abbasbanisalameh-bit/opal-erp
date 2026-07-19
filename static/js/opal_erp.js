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
