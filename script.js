const INDUSTRIES = [
  "반도체",
  "IT/소프트웨어",
  "바이오/헬스케어",
  "금융/보험",
  "에너지/유틸리티",
  "자동차/부품",
  "화학/소재",
  "소비재/유통",
  "건설/부동산",
  "통신/미디어",
];

function shuffled(arr) {
  return [...arr].sort(() => Math.random() - 0.5);
}

function renderIndustries() {
  const list = document.getElementById("industry-list");
  const items = shuffled(INDUSTRIES);
  list.innerHTML = "";
  items.forEach((name) => {
    const li = document.createElement("li");
    li.textContent = name;
    li.addEventListener("click", () => {
      list.querySelectorAll("li").forEach((el) => el.classList.remove("selected"));
      li.classList.add("selected");
    });
    list.appendChild(li);
  });
}

function renderDate() {
  const el = document.getElementById("date-label");
  const now = new Date();
  el.textContent = now.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", (e) => {
    e.preventDefault();
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
    item.classList.add("active");
  });
});

renderIndustries();
renderDate();
