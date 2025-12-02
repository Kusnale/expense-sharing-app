document.addEventListener("DOMContentLoaded", function () {
    var toastElements = document.querySelectorAll(".toast");

    toastElements.forEach((toastEl) => {
        var toast = new bootstrap.Toast(toastEl, {
            delay: 2000, // Auto hide after 2 seconds
            autohide: true
        });
        toast.show();
    });
});
