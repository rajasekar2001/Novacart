document.addEventListener("DOMContentLoaded", () => {
  const checkoutPage = document.querySelector(".checkout-page");
  const pincodeInput = document.querySelector("#id_pincode");
  const countryInput = document.querySelector("#id_country");
  const stateInput = document.querySelector("#id_state");
  const cityInput = document.querySelector("#id_city");
  const lookupButton = document.querySelector("#lookup-pincode");
  const statusElement = document.querySelector("#pincode-status");

  if (
    !checkoutPage ||
    !pincodeInput ||
    !countryInput ||
    !stateInput ||
    !cityInput ||
    !lookupButton ||
    !statusElement
  ) {
    console.error("Checkout pincode elements were not found.");
    return;
  }

  let lastSuccessfulPincode = "";

  function setStatus(message, type = "") {
    statusElement.textContent = message;
    statusElement.className = type;
  }

  function setLocationReadonly(readonly) {
    countryInput.readOnly = readonly;
    stateInput.readOnly = readonly;
    cityInput.readOnly = readonly;
  }

  function clearLocation() {
    countryInput.value = "";
    stateInput.value = "";
    cityInput.value = "";
    setLocationReadonly(false);
  }

  function cleanDivision(value) {
    return String(value || "")
      .replace(
        /\s+(?:g\.?p\.?o\.?\s+)?division$|\s+g\.?p\.?o\.?$/i,
        ""
      )
      .trim();
  }

  function validPlace(value) {
    if (!value) {
      return false;
    }

    const normalized = String(value).trim().toLowerCase();

    return !["na", "n/a", "none", "null", "undefined"].includes(
      normalized
    );
  }

  function getCityFromPostOffice(postOffice) {
    const candidates = [
      cleanDivision(postOffice.Division),
      postOffice.Block,
      postOffice.Taluk,
      postOffice.District,
      postOffice.Name,
    ];

    const city = candidates.find(validPlace);

    return city ? String(city).trim() : "";
  }

  async function postalApiFallback(pincode) {
    const apiUrl =
      `https://api.postalpincode.in/pincode/` +
      encodeURIComponent(pincode);

    const response = await fetch(apiUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Postal API is unavailable.");
    }

    const payload = await response.json();
    const result = payload?.[0];

    if (
      !result ||
      String(result.Status).toLowerCase() !== "success" ||
      !Array.isArray(result.PostOffice) ||
      result.PostOffice.length === 0
    ) {
      throw new Error("Pincode location was not found.");
    }

    const postOffice = result.PostOffice[0];
    const city = getCityFromPostOffice(postOffice);
    const state = String(postOffice.State || "").trim();
    const country = String(postOffice.Country || "India").trim();

    if (!city || !state) {
      throw new Error("Incomplete pincode information.");
    }

    return {
      pincode,
      city,
      state,
      country,
      country_code: "IN",
    };
  }

  async function backendLookup(pincode) {
    const urlTemplate =
      checkoutPage.dataset.pincodeUrlTemplate;

    if (!urlTemplate) {
      throw new Error(
        "Pincode URL template is missing from checkout page."
      );
    }

    const url = urlTemplate.replace(
      "PINCODE",
      encodeURIComponent(pincode)
    );

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    let data;

    try {
      data = await response.json();
    } catch (error) {
      throw new Error("The server returned an invalid response.");
    }

    if (
      response.ok &&
      data.ok &&
      data.location
    ) {
      return data.location;
    }

    throw new Error(
      data.message || "Backend pincode lookup failed."
    );
  }

  function displayLocation(location) {
    countryInput.value = location.country || "India";
    stateInput.value = location.state || "";
    cityInput.value = location.city || "";

    setLocationReadonly(true);

    setStatus(
      `${cityInput.value}, ${stateInput.value}, ` +
      `${countryInput.value}`,
      "lookup-success"
    );
  }

  async function lookupPincode() {
    const pincode = pincodeInput.value
      .replace(/\D/g, "")
      .slice(0, 6);

    pincodeInput.value = pincode;

    if (!/^[1-9][0-9]{5}$/.test(pincode)) {
      lastSuccessfulPincode = "";
      clearLocation();

      setStatus(
        "Enter a valid six-digit Indian pincode.",
        "lookup-error"
      );

      return;
    }

    lookupButton.disabled = true;
    setLocationReadonly(true);

    setStatus(
      "Finding city, state and country...",
      "lookup-loading"
    );

    try {
      let location;

      try {
        location = await backendLookup(pincode);
      } catch (backendError) {
        console.warn(
          "Backend lookup failed. Trying browser fallback:",
          backendError
        );

        location = await postalApiFallback(pincode);
      }

      displayLocation(location);
      lastSuccessfulPincode = pincode;
    } catch (error) {
      console.error("Pincode lookup failed:", error);

      lastSuccessfulPincode = "";
      clearLocation();

      setStatus(
        "Automatic lookup failed. Please enter country, " +
          "state and city manually.",
        "lookup-error"
      );
    } finally {
      lookupButton.disabled = false;
    }
  }

  lookupButton.addEventListener("click", (event) => {
    event.preventDefault();
    lookupPincode();
  });

  pincodeInput.addEventListener("input", () => {
    const cleanedValue = pincodeInput.value
      .replace(/\D/g, "")
      .slice(0, 6);

    pincodeInput.value = cleanedValue;

    if (cleanedValue !== lastSuccessfulPincode) {
      clearLocation();
      setStatus("");
    }

    if (
      cleanedValue.length === 6 &&
      cleanedValue !== lastSuccessfulPincode
    ) {
      lookupPincode();
    }
  });

  pincodeInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      lookupPincode();
    }
  });

  if (
    /^[1-9][0-9]{5}$/.test(pincodeInput.value.trim())
  ) {
    lookupPincode();
  }

  console.log("NovaCart checkout pincode script loaded.");
});