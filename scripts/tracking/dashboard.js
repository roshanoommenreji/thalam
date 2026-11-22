// The dashboard's only script: one view at a time, chosen by the address's #name.
// #<view> opens that view. Any other #name that is an element on the page (a phase, a card in a
// diagram's list, a flow, a glossary term) opens the view holding it and scrolls to it, unfolding
// it if it folds. Inlined by dashboard.py.
(function () {
  var sections = Array.prototype.slice.call(document.querySelectorAll("section.view"));
  var views = sections.map(function (s) { return s.id.replace(/^view-/, ""); });
  function show() {
    var name = (location.hash || "").slice(1), target = null, view = "board";
    if (views.indexOf(name) >= 0) {
      view = name;
    } else if (name && /^[A-Za-z0-9-]+$/.test(name)) {
      target = document.getElementById(name);
      var holder = target && target.closest("section.view");
      if (holder) { view = holder.id.replace(/^view-/, ""); } else { target = null; }
    }
    sections.forEach(function (s) { s.hidden = s.id !== "view-" + view; });
    document.querySelectorAll(".tabs a").forEach(function (a) {
      if (a.getAttribute("href") === "#" + view) { a.setAttribute("aria-current", "page"); }
      else { a.removeAttribute("aria-current"); }
    });
    if (target) {
      if (target.tagName === "DETAILS") { target.open = true; }
      target.classList.add("flash");
      setTimeout(function () { target.classList.remove("flash"); }, 1600);
      target.scrollIntoView({ block: "start" });
    }
  }
  window.addEventListener("hashchange", show);
  show();
})();
