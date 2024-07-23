document.addEventListener("htmx:afterRequest", function(evt) {
    if (evt.detail.xhr.status >= 400 && evt.detail.xhr.status < 600) {
        const toastBoostrap = bootstrap.Toast.getOrCreateInstance(document.getElementById('toasts'));
        toastBoostrap.show();
    }
});