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
