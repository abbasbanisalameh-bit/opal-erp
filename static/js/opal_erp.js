document.addEventListener("DOMContentLoaded", function () {

    console.log("OPAL School ERP Loaded");

    // تفعيل العنصر الحالي في القائمة
    document.querySelectorAll(".opal-menu a").forEach(link => {
        if (link.href === window.location.href) {
            link.classList.add("active");
        }
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


// OPAL_TABLE_SCROLL_INIT_V2
(function () {
    "use strict";

    function initializeScrollableTables(scope) {
        var root = scope || document;
        root.querySelectorAll(".table-responsive, .table-wrap").forEach(function (container) {
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
        document.addEventListener("DOMContentLoaded", function () {
            initializeScrollableTables(document);
        });
    } else {
        initializeScrollableTables(document);
    }

    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === 1) {
                    initializeScrollableTables(node);
                }
            });
        });
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });
})();


// OPAL_BACKUP_ACTIONS_GLOBAL_V3
(function () {
    "use strict";

    var renderTimer = null;

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) {
            return input.value;
        }
        var cookies = document.cookie ? document.cookie.split(";") : [];
        for (var index = 0; index < cookies.length; index += 1) {
            var item = cookies[index].trim();
            if (item.indexOf("csrftoken=") === 0) {
                return decodeURIComponent(item.substring("csrftoken=".length));
            }
        }
        return "";
    }

    function updatesTable() {
        var headings = Array.prototype.slice.call(
            document.querySelectorAll("h1,h2,h3,h4,h5,strong")
        );
        var heading = headings.find(function (element) {
            return (element.textContent || "").indexOf("النسخ المحفوظة على النظام") !== -1;
        });
        if (heading) {
            var current = heading.parentElement;
            while (current && current !== document.body) {
                var found = current.querySelector("table");
                if (found) {
                    return found;
                }
                current = current.parentElement;
            }
        }
        return Array.prototype.slice.call(document.querySelectorAll("table")).find(function (table) {
            var text = table.textContent || "";
            return text.indexOf("الاستعادة") !== -1
                && text.indexOf("Commit") !== -1
                && text.indexOf("الحجم") !== -1;
        }) || null;
    }

    function filenameFromRow(row) {
        var preferred = row.querySelector(".text-break");
        var value = preferred ? (preferred.textContent || "").trim() : "";
        if (/\.zip$/i.test(value)) {
            return value;
        }
        var match = (row.textContent || "").match(/[^\s<>]+\.zip/i);
        return match ? match[0].trim() : "";
    }

    function ensureHeader(table) {
        var row = table.querySelector("thead tr");
        if (!row) {
            return;
        }
        var headers = Array.prototype.slice.call(row.querySelectorAll("th"));
        var actionHeaders = headers.filter(function (header) {
            var text = (header.textContent || "").trim();
            return header.hasAttribute("data-opal-backup-actions-header")
                || header.hasAttribute("data-opal-file-actions-v3-header")
                || text === "ملف النسخة"
                || text === "التنزيل والحذف";
        });
        var header = actionHeaders.shift();
        if (!header) {
            header = document.createElement("th");
            row.appendChild(header);
        }
        header.textContent = "ملف النسخة";
        header.setAttribute("data-opal-backup-actions-header", "true");
        header.setAttribute("data-opal-file-actions-v3-header", "true");
        actionHeaders.forEach(function (duplicate) {
            duplicate.remove();
        });
    }

    function makeActions(row, filename) {
        var cell = row.querySelector("[data-opal-backup-actions]")
            || row.querySelector("[data-opal-file-actions-v3]");
        if (!cell) {
            cell = document.createElement("td");
            row.appendChild(cell);
        }
        cell.setAttribute("data-opal-backup-actions", "true");
        cell.setAttribute("data-opal-file-actions-v3", filename);

        var existingDownload = cell.querySelector(".opal-v3-download");
        var existingDelete = cell.querySelector(".opal-v3-delete");
        if (existingDownload && existingDelete && cell.dataset.opalFileActionsV3 === filename) {
            return;
        }

        cell.innerHTML = "";
        var wrapper = document.createElement("div");
        wrapper.className = "opal-backup-file-actions";

        var download = document.createElement("a");
        download.className = "btn btn-sm btn-outline-info opal-v3-download";
        download.href = "/settings/updates/files/download/?name=" + encodeURIComponent(filename);
        download.setAttribute("download", filename);
        download.innerHTML = '<i class="bi bi-download"></i> تنزيل';

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "btn btn-sm btn-outline-danger opal-v3-delete";
        remove.innerHTML = '<i class="bi bi-trash3"></i> حذف';
        remove.addEventListener("click", function () {
            if (!window.confirm("سيتم حذف ملف النسخة وملف JSON المرتبط به نهائيًا. هل تريد المتابعة؟\n\n" + filename)) {
                return;
            }
            remove.disabled = true;
            remove.textContent = "جاري الحذف...";
            var body = new URLSearchParams();
            body.set("name", filename);
            fetch("/settings/updates/files/delete/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-CSRFToken": csrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: body.toString()
            }).then(function (response) {
                return response.json().then(function (payload) {
                    if (!response.ok || !payload.ok) {
                        throw new Error(payload.message || "تعذر حذف النسخة.");
                    }
                    return payload;
                });
            }).then(function () {
                row.remove();
                window.alert("تم حذف النسخة وملف معلوماتها بنجاح.");
            }).catch(function (error) {
                remove.disabled = false;
                remove.innerHTML = '<i class="bi bi-trash3"></i> حذف';
                window.alert(error.message || "حدث خطأ أثناء حذف النسخة.");
            });
        });

        wrapper.appendChild(download);
        wrapper.appendChild(remove);
        cell.appendChild(wrapper);
    }

    function renderBackupActions() {
        var table = updatesTable();
        if (!table) {
            return;
        }
        ensureHeader(table);
        Array.prototype.slice.call(table.querySelectorAll("tbody tr")).forEach(function (row) {
            if (!row.querySelector("td")) {
                return;
            }
            var filename = filenameFromRow(row);
            if (!filename) {
                return;
            }
            makeActions(row, filename);
        });
    }

    function scheduleRender() {
        window.clearTimeout(renderTimer);
        renderTimer = window.setTimeout(renderBackupActions, 80);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            renderBackupActions();
            window.setTimeout(renderBackupActions, 700);
            window.setTimeout(renderBackupActions, 1800);
        });
    } else {
        renderBackupActions();
        window.setTimeout(renderBackupActions, 700);
    }

    var observer = new MutationObserver(scheduleRender);
    observer.observe(document.documentElement, {childList: true, subtree: true});
})();


// OPAL_TABLE_SCROLL_INIT_V4
(function () {
    "use strict";
    function prepare(scope) {
        var root = scope || document;
        root.querySelectorAll(".opal-main table").forEach(function (table) {
            if (table.closest("[data-opal-no-scroll-table]")) { return; }
            var host = table.parentElement;
            if (!host || !(host.classList.contains("table-responsive") || host.classList.contains("table-wrap") || host.classList.contains("opal-table-viewport"))) {
                host = document.createElement("div");
                host.className = "table-responsive opal-table-viewport opal-table-scroll";
                table.parentNode.insertBefore(host, table);
                host.appendChild(table);
            } else {
                host.classList.add("opal-table-viewport", "opal-table-scroll");
            }
            if (!host.hasAttribute("tabindex")) { host.setAttribute("tabindex", "0"); }
            host.setAttribute("role", "region");
            host.setAttribute("aria-label", "جدول قابل للتمرير مع رأس ثابت");
        });
    }
    function start() { prepare(document); }
    if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); } else { start(); }
    new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === 1) { prepare(node.matches && node.matches("table") ? node.parentElement : node); }
            });
        });
    }).observe(document.documentElement, {childList: true, subtree: true});
})();
