// --- Clean professional avatar styles --- //
const avatarSets = [
    "https://api.dicebear.com/9.x/miniavs/svg",       // Cute minimalist animals
    "https://api.dicebear.com/9.x/open-peeps/svg",   // Hand drawn, soft style
    "https://api.dicebear.com/9.x/fluent-emoji/svg"  // Clean emoji style
];

// Pick random style but always based on username so it stays same
const user = "{{ request.user.username }}";
const avatarUrl = `${avatarSets[Math.floor(Math.random()*avatarSets.length)]}?seed=${encodeURIComponent(user)}`;

// Apply avatar
document.getElementById("profileAvatar").src = avatarUrl;


// Sidebar Open/Close Logic
function openProfile() {
    document.getElementById("profileSidebar").classList.add("active");
    document.getElementById("overlay").classList.add("active");
}

function closeProfile() {
    document.getElementById("profileSidebar").classList.remove("active");
    document.getElementById("overlay").classList.remove("active");
}


// UPI Edit Logic
document.getElementById("upiEditBtn").addEventListener("click", function () {
    let input = document.getElementById("upiInput");

    if (input.disabled) {
        input.disabled = false;
        input.focus();
        this.classList.replace("bi-pencil-square", "bi-check-circle");
        this.style.color = "#3b9c3f";
    } else {
        input.disabled = true;
        this.classList.replace("bi-check-circle", "bi-pencil-square");
        this.style.color = "#00a676";
        alert("UPI Updated ✔");
    }
});
function saveUpi() {
    const upi = document.getElementById("upiInput").value;

    fetch("/save-upi/", {
        method: "POST",
        headers: {
            "X-CSRFToken": csrftoken,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ upi: upi })
    }).then(res => {
        showToast("UPI ID Updated!");
    });
}
