const INDUSTRIES = [
  { name: "반도체",       sub: ["메모리", "시스템반도체", "장비/소재"] },
  { name: "IT/소프트웨어", sub: ["SW/플랫폼", "인터넷", "게임"] },
  { name: "바이오/헬스케어", sub: ["제약", "의료기기", "바이오텍"] },
  { name: "금융/보험",    sub: ["은행", "증권", "보험"] },
  { name: "에너지/유틸리티", sub: ["정유", "신재생에너지", "전력"] },
  { name: "자동차/부품",  sub: ["완성차", "부품", "전기차"] },
  { name: "화학/소재",    sub: ["석유화학", "특수화학", "철강"] },
  { name: "소비재/유통",  sub: ["유통", "음식료", "의류"] },
  { name: "건설/부동산",  sub: ["건설", "부동산", "인프라"] },
  { name: "통신/미디어",  sub: ["통신", "방송", "콘텐츠"] },
];

const ARROW_SVG = `<svg class="arrow-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

function renderIndustries() {
  const list = document.getElementById("industry-list");
  list.innerHTML = "";

  INDUSTRIES.forEach(({ name, sub }) => {
    const item = document.createElement("li");
    item.className = "industry-item";

    const header = document.createElement("div");
    header.className = "industry-header";
    header.innerHTML = `<span>${name}</span>${ARROW_SVG}`;

    const subList = document.createElement("ul");
    subList.className = "sub-list";
    sub.forEach((subName) => {
      const subLi = document.createElement("li");
      subLi.textContent = subName;
      subLi.addEventListener("click", (e) => {
        e.stopPropagation();
        list.querySelectorAll(".sub-list li").forEach((el) => el.classList.remove("selected"));
        subLi.classList.add("selected");
      });
      subList.appendChild(subLi);
    });

    header.addEventListener("click", () => {
      const isOpen = item.classList.contains("open");
      list.querySelectorAll(".industry-item").forEach((el) => el.classList.remove("open"));
      if (!isOpen) item.classList.add("open");
    });

    item.appendChild(header);
    item.appendChild(subList);
    list.appendChild(item);
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
