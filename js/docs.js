/* Docs pages only. Collapses the sidebar on small screens.
   The landing page does not load this file. */
(function () {
    var sidebar = document.getElementById('docsSidebar');
    var btn = document.getElementById('docsMenuToggle');
    if (!sidebar || !btn) return;

    function setOpen(open) {
        sidebar.classList.toggle('is-open', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (!open) return;
        var active = sidebar.querySelector('.docs-nav-link.active');
        if (active && active.scrollIntoView) {
            active.scrollIntoView({ block: 'nearest' });
        }
    }

    btn.addEventListener('click', function () {
        setOpen(btn.getAttribute('aria-expanded') !== 'true');
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
            setOpen(false);
            btn.focus();
        }
    });
})();
