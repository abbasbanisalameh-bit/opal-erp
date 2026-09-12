(function () {
    "use strict";

    var toggle = document.querySelector(".learning-menu-toggle");
    var nav = document.getElementById("learning-nav");
    if (!toggle || !nav) return;

    function closeMenu() {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "فتح القائمة");
    }

    toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "إغلاق القائمة" : "فتح القائمة");
    });

    nav.addEventListener("click", function (event) {
        if (event.target.closest("a")) closeMenu();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeMenu();
    });
})();
