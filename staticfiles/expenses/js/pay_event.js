document.addEventListener("DOMContentLoaded", () => {
  console.log("💡 pay_event.js loaded");

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let cookie of cookies) {
        const c = cookie.trim();
        if (c.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(c.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // --- CASH PAYMENT ---
  document.querySelectorAll(".cash-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const amount = btn.dataset.amount;
      const receiver = btn.dataset.receiver;

      document.getElementById("cash-text").textContent = `Record cash payment of ₹${amount} to ${receiver}?`;
      document.getElementById("cash-popup").style.display = "flex";

      const confirm = document.getElementById("cash-confirm");
      const cancel = document.getElementById("cash-cancel");

      cancel.onclick = () => (document.getElementById("cash-popup").style.display = "none");

      confirm.onclick = async () => {
        console.log("💵 Recording cash payment:", { receiver, amount });
        const response = await fetch(recordPaymentURL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: JSON.stringify({
            payee: receiver,
            amount: amount,
            method: "Cash",
          }),
        });

        const data = await response.json();
        alert(data.message || data.error);
        if (data.success) location.reload();
      };
    });
  });

  // --- UPI PAYMENT ---
  document.querySelectorAll(".upi-btn").forEach((btn) => {
    btn.addEventListener("click",function ()  {
      
      const amount = btn.dataset.amount;
      const receiver = btn.dataset.receiver;

      document.getElementById("upi-popup").style.display = "flex";
      document.getElementById("upi-amount").innerText = "₹" + this.dataset.amount;
      document.getElementById("upi-receiver").innerText = this.dataset.receiver;
      document.getElementById("upi-id").innerText = this.dataset.upi || "Not available";
   

      const confirm = document.getElementById("upi-confirm");
      const cancel = document.getElementById("upi-cancel");

      cancel.onclick = () => (document.getElementById("upi-popup").style.display = "none");

      confirm.onclick = () => {
        const receiverUPI = document.getElementById("upi-id").innerText.trim();
        const amount = document.getElementById("upi-amount").innerText.replace("₹", "").trim();
        const receiverName = document.getElementById("upi-receiver").innerText.trim();

        if (!receiverUPI || receiverUPI === "Not available") {
          alert("Receiver has no UPI ID set!");
          return;
        }

        // Create a unique transaction id to track after redirect
        const txnId = "TXN" + Date.now();

        // Your site URL (update if you’re running locally on something else)
        const redirectUrl = `${window.location.origin}/expenses/upi-success/?txn_id=${txnId}&receiver=${encodeURIComponent(receiverName)}&amount=${amount}`;

        const upiUrl = `upi://pay?pa=${receiverUPI}&pn=${receiverName}&am=${amount}&cu=INR&tn=${txnId}&tr=${txnId}&url=${encodeURIComponent(redirectUrl)}`;

        console.log("🔗 Opening UPI intent:", upiUrl);

        // Redirect to UPI intent
        window.location.href = upiUrl;
      };


    });
  });
});
