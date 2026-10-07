"use strict";

// Border under the sticky header once the page scrolls.
const nav = document.getElementById("nav");
const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();

// Pause control for the moving list of services (WCAG 2.2.2).
const marquee = document.getElementById("marquee");
const pause = document.getElementById("pause");
pause.addEventListener("click", () => {
  const paused = marquee.classList.toggle("paused");
  pause.setAttribute("aria-pressed", String(paused));
  pause.textContent = paused ? "Play" : "Pause";
});

document.getElementById("year").textContent = new Date().getFullYear();
