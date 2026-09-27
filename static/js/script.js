document.addEventListener("DOMContentLoaded", function () {
  var fileInputs = document.querySelectorAll('input[type="file"]');
  fileInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      if (input.files.length > 0) {
        input.classList.add("border-emerald-500");
      }
    });
  });

  var flashMessages = document.querySelectorAll(".rounded.bg-red-100, .rounded.bg-green-100");
  flashMessages.forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.5s";
      el.style.opacity = "0";
    }, 5000);
  });
});
