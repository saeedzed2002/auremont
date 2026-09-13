const menuButton = document.querySelector("[data-menu-button]");
const mobileMenu = document.querySelector("[data-mobile-menu]");
const menuLabel = document.querySelector("[data-menu-label]");

if (menuButton && mobileMenu) {
  menuButton.addEventListener("click", () => {
    const isOpen = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isOpen));
    mobileMenu.classList.toggle("hidden", isOpen);
    if (menuLabel) {
      menuLabel.textContent = isOpen ? "Open navigation" : "Close navigation";
    }
  });
}

document.querySelectorAll(".field-has-errors .errorlist").forEach((errorList) => {
  const field = errorList.parentElement?.querySelector("input, textarea, select");
  if (!field || !errorList.id) {
    return;
  }

  field.setAttribute("aria-invalid", "true");
  field.setAttribute("aria-describedby", errorList.id);
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post") {
    return;
  }
  if (form.dataset.submitting === "true") {
    event.preventDefault();
    return;
  }

  form.dataset.submitting = "true";
  form.setAttribute("aria-busy", "true");
  form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(
    (control) => {
      control.disabled = true;
    },
  );

  const submitter = event.submitter;
  if (!(submitter instanceof HTMLButtonElement)) {
    return;
  }

  submitter.classList.add("is-loading");
  submitter.textContent = submitter.dataset.loadingLabel || "Working…";
});

const tehranClock = document.querySelector("[data-tehran-clock]");

if (tehranClock) {
  const hourHand = tehranClock.querySelector("[data-clock-hour]");
  const minuteHand = tehranClock.querySelector("[data-clock-minute]");
  const secondHand = tehranClock.querySelector("[data-clock-second]");
  const digitalTime = tehranClock.querySelector("[data-clock-digital]");
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Tehran",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });

  const setHandAngle = (hand, degrees) => {
    hand.style.transform = `translateY(-50%) rotate(${degrees - 90}deg)`;
  };

  const updateTehranClock = () => {
    const now = new Date();
    const time = Object.fromEntries(
      formatter
        .formatToParts(now)
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, part.value]),
    );
    const hour = Number(time.hour);
    const minute = Number(time.minute);
    const second = Number(time.second);

    setHandAngle(hourHand, (hour % 12) * 30 + minute * 0.5 + second / 120);
    setHandAngle(minuteHand, minute * 6 + second / 10);
    setHandAngle(secondHand, second * 6);
    digitalTime.textContent = `${time.hour}:${time.minute}:${time.second}`;
    digitalTime.dateTime = now.toISOString();

    window.setTimeout(updateTehranClock, 1000 - (Date.now() % 1000));
  };

  if (hourHand && minuteHand && secondHand && digitalTime) {
    updateTehranClock();
  }
}
