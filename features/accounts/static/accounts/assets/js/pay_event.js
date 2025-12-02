// static/accounts/assets/js/pay_event.js
document.addEventListener("DOMContentLoaded", () => {
  console.log("💡 pay_event.js loaded");

  // Helpers
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
  const hide = el => { if (el) el.style.display = "none"; };
  const show = el => { if (el) el.style.display = "flex"; };
  const getCookie = (name) => {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let c of cookies) {
      c = c.trim();
      if (c.startsWith(name + '=')) return decodeURIComponent(c.substring(name.length+1));
    }
    return null;
  };

  // Elements (popups)
  const cashPopup = $("#cash-popup");
  const cashText = $("#cash-text");
  const cashConfirm = $("#cash-confirm");
  const cashCancel = $("#cash-cancel");

  const upiPopup = $("#upi-popup");
  const upiAmountSpan = $("#upi-amount");
  const upiReceiverSpan = $("#upi-receiver");
  const upiIdSpan = $("#upi-id");
  const upiInput = $("#upi-input");
  const upiConfirm = $("#upi-confirm");
  const upiCancel = $("#upi-cancel");

  // ---- CASH PAYMENTS ----
  $$(".cash-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const amount = btn.dataset.amount;
      const receiver = btn.dataset.receiver;

      cashText.textContent = `Record cash payment of ₹${amount} to ${receiver}?`;
      show(cashPopup);

      cashCancel.onclick = () => hide(cashPopup);

      cashConfirm.onclick = async () => {
        try {
          if (typeof recordPaymentURL === "undefined") {
            hide(cashPopup);
            alert("Cash recorded locally. Reloading...");
            location.reload();
            return;
          }

          const resp = await fetch(recordPaymentURL, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify({ payee: receiver, amount: amount, method: "Cash" })
          });

          const data = await resp.json();
          if (data.success) {
            alert(`✅ Cash payment of ₹${amount} recorded for ${receiver}`);
            hide(cashPopup);
            updateSettlementUI(receiver, amount, "Cash");
          } else {
            alert(data.error || "Failed to record cash payment.");
            hide(cashPopup);
          }
        } catch (err) {
          console.error(err);
          alert("Failed to record cash payment.");
          hide(cashPopup);
        }
      };
    });
  });

  // ---- UPI PAYMENTS ----
  $$(".upi-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const amount = btn.dataset.amount;
      const receiverName = btn.dataset.receiver;
      const receiverUpi = btn.dataset.upi || "";

      // Fill popup fields
      upiAmountSpan.innerText = "₹" + amount;
      upiReceiverSpan.innerText = receiverName;
      upiIdSpan.innerText = receiverUpi || "Not available";
      upiInput.value = receiverUpi || "";  // Autofill if available

      show(upiPopup);

      upiCancel.onclick = () => {
        hide(upiPopup);
        upiInput.value = "";
      };

      upiConfirm.onclick = () => {
        let finalReceiverUpi = receiverUpi.trim();
        const typedUpi = upiInput.value.trim();

        // If profile UPI missing → use typed UPI
        if (!finalReceiverUpi) {
          finalReceiverUpi = typedUpi;
        }

        // Validate final receiver UPI
        if (!finalReceiverUpi || !finalReceiverUpi.includes("@")) {
          alert("Enter a valid receiver UPI ID!");
          return;
        }

        // Validate sender UPI
        if (!typedUpi || !typedUpi.includes("@")) {
          alert("Enter your UPI ID (your own UPI)");
          return;
        }

        const amountText = upiAmountSpan.innerText.replace("₹", "").trim();

        
        const upiUrl =
          "upi://pay?" +
          "pa=" + encodeURIComponent(finalReceiverUpi) +
          "&pn=" + encodeURIComponent(receiverName) +
          "&am=" + encodeURIComponent(amountText) +
          "&cu=INR" +
          "&tn=" + encodeURIComponent("Event payment") +
          "&mode=00" +
          "&orgid=000000" +
          "&sign=000000";


        console.log("Opening UPI URL:", upiUrl);


        hide(upiPopup);
        window.location.href = upiUrl;

        // Strict UPI regex (prevents invalid VPA causing GPay errors)
        const upiRegex = /^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$/;

        if (!upiRegex.test(finalReceiverUpi)) {
            alert("Receiver UPI ID is invalid or not activated!");
            return;
        }

        if (!upiRegex.test(typedUpi)) {
            alert("Enter a valid active UPI ID (your UPI)");
            return;
        }

        // Optional DB save
        if (typeof recordPaymentURL !== "undefined") {
          fetch(recordPaymentURL, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify({ payee: receiverName, amount: amountText, method: "UPI" })
          }).then(r => r.json()).then(d => {
            if (d.success) {
              updateSettlementUI(receiverName, amountText, "UPI");
            }
          });
        }
      };
    });
  });

  // ---- Update Settlement UI ----
  function updateSettlementUI(receiver, amount, method) {
    $$(".cash-btn, .upi-btn").forEach(btn => {
      if (btn.dataset.receiver === receiver) {
        const parentDiv = btn.closest("div[style*='border']");
        if (!parentDiv) return;

        let paidLabel = parentDiv.querySelector(".paid-label");
        if (!paidLabel) {
          paidLabel = document.createElement("div");
          paidLabel.className = "paid-label";
          paidLabel.style.color = "#4CAF50";
          paidLabel.style.fontWeight = "600";
          paidLabel.style.marginTop = "10px";
          parentDiv.appendChild(paidLabel);
        }
        paidLabel.innerText = `Paid via ${method} ₹${amount}`;
      }
    });
  }

});
