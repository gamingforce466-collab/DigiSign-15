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
<<<<<<< HEAD

  initKeyForm();
  initSignForm();
});

/* Tombol "Isi acak" (fitur uji). Passphrase kunci acak hanya disimpan
 * di sessionStorage tab ini agar form tanda tangan bisa terisi otomatis. */
var KNOWN_KEYS_STORE = "digisign_random_keys";

function loadKnownKeys() {
  try {
    return JSON.parse(sessionStorage.getItem(KNOWN_KEYS_STORE) || "{}");
  } catch (e) {
    return {};
  }
}

function saveKnownKeys(map) {
  try {
    sessionStorage.setItem(KNOWN_KEYS_STORE, JSON.stringify(map));
  } catch (e) { /* sessionStorage tidak tersedia: abaikan */ }
}

function showHint(el, text) {
  if (!el) return;
  el.textContent = text;
  el.classList.remove("hidden");
}

function fetchJson(url, options) {
  options = options || {};
  options.cache = "no-store";
  return fetch(url, options).then(function (response) {
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  });
}

function initKeyForm() {
  var button = document.getElementById("btn-random-key");
  if (!button) return;
  var ownerInput = document.getElementById("key-owner-input");
  var passInput = document.getElementById("key-pass-input");
  var hint = document.getElementById("key-random-hint");

  button.addEventListener("click", function () {
    button.disabled = true;
    fetchJson("/api/random").then(function (data) {
      ownerInput.value = data.owner_id;
      passInput.type = "text";
      passInput.value = data.passphrase;
      var known = loadKnownKeys();
      known[data.owner_id] = data.passphrase;
      saveKnownKeys(known);
      showHint(hint, "Terisi. Klik Buat Kunci. Passphrase: " + data.passphrase);
    }).catch(function (err) {
      showHint(hint, "Gagal mengambil data: " + err.message);
    }).then(function () {
      button.disabled = false;
    });
  });
}

function initSignForm() {
  var form = document.getElementById("sign-form");
  if (!form) return;
  var docSelect = document.getElementById("doc-select");
  var ownerSelect = document.getElementById("owner-select");
  var passInput = document.getElementById("sign-pass");
  var nameInput = document.getElementById("sign-name");
  var positionInput = document.getElementById("sign-position");
  var institutionInput = document.getElementById("sign-institution");
  var dateInput = document.getElementById("sign-date");
  var fileInput = document.getElementById("pdf-file");
  var hint = document.getElementById("sign-random-hint");
  var button = document.getElementById("btn-random-sign");

  function syncPdfControls() {
    var isNewDocument = !docSelect.value;
    fileInput.disabled = !isNewDocument;
    fileInput.parentElement.style.opacity = isNewDocument ? "1" : "0.4";
  }

  docSelect.addEventListener("change", syncPdfControls);
  syncPdfControls();

  ownerSelect.addEventListener("change", function () {
    var known = loadKnownKeys();
    if (known[ownerSelect.value]) passInput.value = known[ownerSelect.value];
  });

  if (!button) return;

  button.addEventListener("click", function () {
    button.disabled = true;
    var note = "";
    fetchJson("/api/random").then(function (data) {
      nameInput.value = data.signer_name;
      positionInput.value = data.position;
      institutionInput.value = data.institution;
      dateInput.value = data.signed_date;

      var selected = docSelect.options[docSelect.selectedIndex];
      var used = ((selected && selected.dataset.owners) || "").split(",").filter(Boolean);
      var known = loadKnownKeys();
      var available = Array.prototype.map.call(ownerSelect.options, function (o) { return o.value; })
        .filter(function (v) { return v && known[v] && used.indexOf(v) === -1; });

      if (available.length) {
        note = "kunci lama dipakai";
        return available[Math.floor(Math.random() * available.length)];
      }
      showHint(hint, "Membuat kunci baru...");
      return fetchJson("/api/random_key", { method: "POST" }).then(function (created) {
        known[created.owner_id] = created.passphrase;
        saveKnownKeys(known);
        var option = document.createElement("option");
        option.value = created.owner_id;
        option.textContent = created.owner_id;
        ownerSelect.appendChild(option);
        note = "kunci baru dibuat";
        return created.owner_id;
      });
    }).then(function (owner) {
      var known = loadKnownKeys();
      ownerSelect.value = owner;
      passInput.value = known[owner] || "";
      syncPdfControls();
      var next = docSelect.value
        ? "Klik Tandatangani untuk menambah penandatangan."
        : "Pilih berkas PDF, lalu klik Tandatangani.";
      showHint(hint, "Terisi (" + note + "). " + next);
    }).catch(function (err) {
      showHint(hint, "Gagal mengisi data: " + err.message);
    }).then(function () {
      button.disabled = false;
    });
  });
}
=======
});
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
