/* Homepage quote carousel. Loaded only from index.html.
   With this script absent, the quotes stay stacked in the page. */
(function () {
    var root = document.querySelector('[data-testimonials]');
    if (!root) return;

    var viewport = root.querySelector('.testimonial-viewport');
    var slides = Array.prototype.slice.call(root.querySelectorAll('.testimonial-slide'));
    var prevBtn = root.querySelector('.testimonial-prev');
    var nextBtn = root.querySelector('.testimonial-next');
    var dotsWrap = root.querySelector('.testimonial-dots');
    if (!viewport || !prevBtn || !nextBtn || !dotsWrap || slides.length < 2) return;

    var INTERVAL = 7000;
    var reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    var index = 0;
    var timer = null;
    var hovered = false;
    var keyboardFocus = false;
    var dots = [];

    function reduced() {
        return reduceQuery.matches;
    }

    slides.forEach(function (slide, i) {
        slide.setAttribute('aria-roledescription', 'slide');
        slide.setAttribute('aria-label', (i + 1) + ' of ' + slides.length);

        var dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'testimonial-dot';
        dot.setAttribute('aria-label', 'Show quote ' + (i + 1) + ' of ' + slides.length);
        dot.addEventListener('click', function () { show(i, true); });
        dotsWrap.appendChild(dot);
        dots.push(dot);
    });

    function measure() {
        var max = 0;
        slides.forEach(function (slide) { slide.style.height = 'auto'; });
        slides.forEach(function (slide) {
            if (slide.offsetHeight > max) max = slide.offsetHeight;
        });
        slides.forEach(function (slide) { slide.style.height = ''; });
        if (max > 0) viewport.style.height = max + 'px';
    }

    function show(nextIndex, fromUser) {
        index = (nextIndex + slides.length) % slides.length;
        slides.forEach(function (slide, i) {
            var on = i === index;
            slide.classList.toggle('is-active', on);
            if (on) slide.removeAttribute('aria-hidden');
            else slide.setAttribute('aria-hidden', 'true');
        });
        dots.forEach(function (dot, i) {
            var on = i === index;
            dot.classList.toggle('is-active', on);
            if (on) dot.setAttribute('aria-current', 'true');
            else dot.removeAttribute('aria-current');
        });
        if (fromUser) arm();
    }

    function stop() {
        if (timer !== null) {
            clearInterval(timer);
            timer = null;
        }
    }

    function paused() {
        return reduced() || hovered || keyboardFocus || document.hidden;
    }

    function arm() {
        stop();
        if (paused()) return;
        timer = setInterval(function () { show(index + 1, false); }, INTERVAL);
    }

    function keyboardFocusInside() {
        var active = document.activeElement;
        return !!(active && root.contains(active) && active.matches && active.matches(':focus-visible'));
    }

    prevBtn.addEventListener('click', function () { show(index - 1, true); });
    nextBtn.addEventListener('click', function () { show(index + 1, true); });

    root.addEventListener('mouseenter', function () {
        hovered = true;
        stop();
    });
    root.addEventListener('mouseleave', function () {
        hovered = false;
        arm();
    });
    root.addEventListener('focusin', function () {
        keyboardFocus = keyboardFocusInside();
        if (keyboardFocus) stop();
    });
    root.addEventListener('focusout', function (event) {
        if (root.contains(event.relatedTarget)) {
            window.setTimeout(function () {
                keyboardFocus = keyboardFocusInside();
                if (!keyboardFocus) arm();
                else stop();
            }, 0);
            return;
        }
        keyboardFocus = false;
        arm();
    });
    root.addEventListener('keydown', function (event) {
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            show(index - 1, true);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            show(index + 1, true);
        }
    });

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) stop();
        else arm();
    });

    function onReduceChange() {
        if (reduced()) stop();
        else arm();
    }
    if (typeof reduceQuery.addEventListener === 'function') {
        reduceQuery.addEventListener('change', onReduceChange);
    } else if (typeof reduceQuery.addListener === 'function') {
        reduceQuery.addListener(onReduceChange);
    }

    var resizeTimer = null;
    window.addEventListener('resize', function () {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(measure, 100);
    });

    root.classList.add('is-ready');
    measure();
    show(0, false);
    arm();

    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(function () { measure(); });
    }
})();
